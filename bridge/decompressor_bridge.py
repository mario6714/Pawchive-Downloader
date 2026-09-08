"""
Decompressor Bridge
Exposes BulkDecompressorEngine to QML with reactive properties,
async worker threads, live progress parsing, and ETA calculations.
"""

import os
import sys
import json
import time
import shutil
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

from PySide6.QtCore import QObject, Signal, Slot, Property
from PySide6.QtWidgets import QFileDialog

from services.bulk_decompressor import (
    BulkDecompressorEngine,
    ArchiveItem,
    DiskCheckResult,
    get_7za_path
)
from core.logger import logger


def _format_bytes(b: int) -> str:
    if not b or b <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024.0:
            return f"{b:.1f} {unit}"
        b /= 1024.0
    return f"{b:.1f} PB"


class DecompressorBridge(QObject):
    # ── Signals ────────────────────────────────────────────────────────────────
    scanStarted = Signal()
    scanFinished = Signal(int, "qint64")  # count, total_bytes (64-bit to prevent 32-bit overflow)
    scanError = Signal(str)

    itemsChanged = Signal()
    isBusyChanged = Signal()
    isScanningChanged = Signal()
    isExtractingChanged = Signal()
    selectedStatsChanged = Signal()
    settingsChanged = Signal()
    locationsChanged = Signal()

    diskCheckCompleted = Signal(str)  # JSON string of List[DiskCheckResult]

    extractionStarted = Signal()
    extractionProgress = Signal(float, str, float, str, str)  # overall%, cur_name, cur_pct, eta_str, speed_str
    itemUpdated = Signal(str, str, float, str)  # id, status, progress, error_message
    extractionFinished = Signal(int, int)  # success_count, error_count

    def __init__(self, watchlist_manager, app_bridge=None, parent=None):
        super().__init__(parent)
        self._watchlist_manager = watchlist_manager
        self._app_bridge = app_bridge
        self.engine = BulkDecompressorEngine()

        self._items: List[ArchiveItem] = []
        self._items_lock = threading.Lock()
        self._custom_locations: List[Dict[str, str]] = []  # [{"path": ..., "creator": ...}]

        # State flags
        self._is_scanning = False
        self._is_extracting = False
        self._scan_cancel_event = threading.Event()
        self._extract_cancel_event = threading.Event()

        # Configurable Settings
        self._max_parallel = 2
        self._threads_per_archive = 2
        self._delete_after = False

        # Metrics for extraction
        self._total_bytes_to_extract = 0
        self._extracted_bytes_done = 0
        self._start_time = 0.0

    # ── Properties ─────────────────────────────────────────────────────────────

    @Property(bool, notify=isBusyChanged)
    def isBusy(self) -> bool:
        return self._is_scanning or self._is_extracting

    @Property(bool, notify=isScanningChanged)
    def isScanning(self) -> bool:
        return self._is_scanning

    @Property(bool, notify=isExtractingChanged)
    def isExtracting(self) -> bool:
        return self._is_extracting

    @Property(int, notify=itemsChanged)
    def totalCount(self) -> int:
        with self._items_lock:
            return len(self._items)

    @Property(int, notify=selectedStatsChanged)
    def selectedCount(self) -> int:
        with self._items_lock:
            return sum(1 for i in self._items if i.selected)

    @Property("qint64", notify=itemsChanged)
    def totalBytes(self) -> int:
        with self._items_lock:
            return sum(i.size for i in self._items)

    @Property("qint64", notify=selectedStatsChanged)
    def selectedBytes(self) -> int:
        with self._items_lock:
            return sum(i.size for i in self._items if i.selected)

    @Property(int, notify=settingsChanged)
    def maxParallel(self) -> int:
        return self._max_parallel

    @maxParallel.setter
    def maxParallel(self, val: int):
        v = max(1, min(8, int(val)))
        if self._max_parallel != v:
            self._max_parallel = v
            self.settingsChanged.emit()

    @Property(int, notify=settingsChanged)
    def threadsPerArchive(self) -> int:
        return self._threads_per_archive

    @threadsPerArchive.setter
    def threadsPerArchive(self, val: int):
        v = max(1, min(16, int(val)))
        if self._threads_per_archive != v:
            self._threads_per_archive = v
            self.settingsChanged.emit()

    @Property(bool, notify=settingsChanged)
    def deleteAfter(self) -> bool:
        return self._delete_after

    @deleteAfter.setter
    def deleteAfter(self, val: bool):
        if self._delete_after != bool(val):
            self._delete_after = bool(val)
            self.settingsChanged.emit()

    @Property(str, notify=itemsChanged)
    def itemsJson(self) -> str:
        with self._items_lock:
            data = [i.to_dict() for i in self._items]
        return json.dumps(data, ensure_ascii=False)

    @Property(str, notify=itemsChanged)
    def groupedItemsJson(self) -> str:
        """Returns archives grouped hierarchically by (creator, scan_root) so that
        the same creator with multiple watched download folders appears as separate groups."""
        with self._items_lock:
            # Key: (creator_name, norm_scan_root) — unique per watched folder, stable across subdirs
            groups_dict: Dict[tuple, Dict[str, Any]] = {}
            for item in self._items:
                c = item.creator or "Unknown"
                raw_root = item.scan_root or item.directory
                norm_root = os.path.normcase(os.path.normpath(raw_root)) if raw_root else ""
                key = (c, norm_root)
                if key not in groups_dict:
                    groups_dict[key] = {
                        "creator": c,
                        "directory": item.scan_root or item.directory,
                        "items": [],
                        "totalCount": 0,
                        "selectedCount": 0,
                        "totalBytes": 0,
                        "selectedBytes": 0,
                    }
                g = groups_dict[key]
                g["items"].append(item.to_dict())
                g["totalCount"] += 1
                g["totalBytes"] += item.size
                if item.selected:
                    g["selectedCount"] += 1
                    g["selectedBytes"] += item.size

            groups_list = list(groups_dict.values())
            for g in groups_list:
                g["allSelected"] = (g["totalCount"] > 0 and g["selectedCount"] == g["totalCount"])
                g["someSelected"] = (g["selectedCount"] > 0 and g["selectedCount"] < g["totalCount"])

        return json.dumps(groups_list, ensure_ascii=False)

    @Property(str, notify=locationsChanged)
    def locationsJson(self) -> str:
        locs = self._get_all_target_locations()
        return json.dumps(locs, ensure_ascii=False)

    @Property(bool, constant=True)
    def has7za(self) -> bool:
        return self.engine.has_7za

    # ── Internal Helpers ───────────────────────────────────────────────────────

    def _get_all_target_locations(self) -> List[Dict[str, str]]:
        """Combine watchlist locations with any user-added custom folder locations."""
        locations = []
        # 1. Watchlist entries
        if self._watchlist_manager:
            for e in self._watchlist_manager.entries:
                p = e.download_dir.strip() if e.download_dir else ""
                # If download_dir not set on entry, check default download folder with creator subfolder
                if not p and self._app_bridge:
                    default_base = getattr(self._app_bridge, "downloadDir", "")
                    if default_base and os.path.exists(default_base):
                        cand = os.path.join(default_base, f"{e.creator_name} [{e.service}]")
                        if os.path.exists(cand):
                            p = cand
                        else:
                            p = default_base
                if p and os.path.exists(p):
                    # If p is a parent directory, check if a dedicated creator subfolder exists inside it
                    if os.path.isdir(p) and e.creator_name:
                        expected = [
                            f"{e.creator_name} [{e.service}]".lower() if e.service else "",
                            e.creator_name.lower()
                        ]
                        try:
                            for sub in os.listdir(p):
                                sub_lower = sub.lower()
                                if any(sub_lower == exp for exp in expected if exp) or (
                                    e.service and sub_lower.startswith(f"{e.creator_name.lower()} [")
                                ):
                                    cand = os.path.join(p, sub)
                                    if os.path.isdir(cand):
                                        p = cand
                                        break
                        except OSError:
                            pass

                    locations.append({
                        "path": p,
                        "creator": e.creator_name or e.user_id,
                        "source": "watchlist"
                    })

        # 2. Custom manually added locations
        for c in self._custom_locations:
            locations.append({
                "path": c["path"],
                "creator": c.get("creator", "Custom"),
                "source": "custom"
            })

        # Deduplicate paths
        unique = []
        seen = set()
        for loc in locations:
            norm = os.path.normcase(os.path.normpath(loc["path"]))
            if norm not in seen:
                seen.add(norm)
                unique.append(loc)
        return unique

    # ── Scanning Slots ─────────────────────────────────────────────────────────

    @Slot()
    def scanLocations(self):
        """Asynchronously scan all configured locations (watchlist + custom) for archives."""
        if self._is_scanning or self._is_extracting:
            return

        self._is_scanning = True
        self._scan_cancel_event.clear()
        self.isScanningChanged.emit()
        self.isBusyChanged.emit()
        self.scanStarted.emit()

        targets = [(loc["path"], loc["creator"]) for loc in self._get_all_target_locations()]
        logger.info(f"Scanning {len(targets)} location(s) for archives...", category="decompressor")

        def _worker():
            try:
                scanned = self.engine.scan_locations(targets, self._scan_cancel_event)
                with self._items_lock:
                    self._items = scanned
                total_sz = sum(i.size for i in scanned)
                self._is_scanning = False
                self.isScanningChanged.emit()
                self.isBusyChanged.emit()
                self.itemsChanged.emit()
                self.selectedStatsChanged.emit()
                self.scanFinished.emit(len(scanned), total_sz)
                logger.info(
                    f"Scan complete: found {len(scanned)} archive(s) ({_format_bytes(total_sz)}).",
                    category="decompressor"
                )
            except Exception as e:
                logger.error(f"Scan error: {e}", category="decompressor")
                self._is_scanning = False
                self.isScanningChanged.emit()
                self.isBusyChanged.emit()
                self.scanError.emit(str(e))

        threading.Thread(target=_worker, daemon=True).start()

    @Slot()
    def browseCustomFolder(self):
        """Open folder dialog to add a custom folder and re-scan."""
        start_dir = getattr(self._app_bridge, "downloadDir", "") if self._app_bridge else ""
        folder = QFileDialog.getExistingDirectory(
            None,
            "Select Folder to Scan for Archives",
            start_dir
        )
        if folder:
            norm = os.path.normcase(os.path.normpath(folder))
            if not any(os.path.normcase(os.path.normpath(c["path"])) == norm for c in self._custom_locations):
                self._custom_locations.append({
                    "path": folder,
                    "creator": os.path.basename(folder) or "Custom",
                    "source": "custom"
                })
                logger.info(f"Added custom folder to decompressor: {folder}", category="decompressor")
                self.locationsChanged.emit()
            self.scanLocations()

    @Slot(int)
    def removeCustomLocation(self, index: int):
        """Remove a custom folder at index."""
        if 0 <= index < len(self._custom_locations):
            self._custom_locations.pop(index)
            self.locationsChanged.emit()

    # ── Selection Slots ────────────────────────────────────────────────────────

    @Slot(bool)
    def selectAll(self, selected: bool):
        with self._items_lock:
            for item in self._items:
                item.selected = selected
        self.itemsChanged.emit()
        self.selectedStatsChanged.emit()

    @Slot(str, bool)
    def selectCreator(self, creatorName: str, selected: bool):
        with self._items_lock:
            for item in self._items:
                if item.creator == creatorName:
                    item.selected = selected
        self.itemsChanged.emit()
        self.selectedStatsChanged.emit()

    @Slot(str, str, bool)
    def selectCreatorByScanRoot(self, creatorName: str, scanRoot: str, selected: bool):
        """Select/deselect all archives for a specific creator+folder pair."""
        norm = os.path.normcase(os.path.normpath(scanRoot)) if scanRoot else ""
        with self._items_lock:
            for item in self._items:
                item_root = os.path.normcase(os.path.normpath(item.scan_root or item.directory))
                if item.creator == creatorName and item_root == norm:
                    item.selected = selected
        self.itemsChanged.emit()
        self.selectedStatsChanged.emit()

    @Slot(str)
    def toggleCreator(self, creatorName: str):
        """Toggle selection for all archives of a specific creator."""
        with self._items_lock:
            creator_items = [i for i in self._items if i.creator == creatorName]
            all_sel = all(i.selected for i in creator_items) if creator_items else False
            new_val = not all_sel
            for item in creator_items:
                item.selected = new_val
        self.itemsChanged.emit()
        self.selectedStatsChanged.emit()

    @Slot(str, str)
    def toggleCreatorByScanRoot(self, creatorName: str, scanRoot: str):
        """Toggle selection for all archives of a specific creator+folder pair."""
        norm = os.path.normcase(os.path.normpath(scanRoot)) if scanRoot else ""
        with self._items_lock:
            creator_items = [i for i in self._items
                             if i.creator == creatorName and os.path.normcase(os.path.normpath(i.scan_root or i.directory)) == norm]
            all_sel = all(i.selected for i in creator_items) if creator_items else False
            new_val = not all_sel
            for item in creator_items:
                item.selected = new_val
        self.itemsChanged.emit()
        self.selectedStatsChanged.emit()

    @Slot(str)
    def toggleItem(self, itemId: str):
        with self._items_lock:
            for item in self._items:
                if item.item_id == itemId:
                    item.selected = not item.selected
                    break
        self.itemsChanged.emit()
        self.selectedStatsChanged.emit()

    # ── Pre-flight Disk Check ──────────────────────────────────────────────────

    @Slot(result=str)
    def checkDiskSpace(self) -> str:
        """Run disk space check and return JSON results."""
        with self._items_lock:
            items_copy = list(self._items)
        results = self.engine.check_disk_space(items_copy, delete_after=self._delete_after)
        data = [r.to_dict() for r in results]
        res_json = json.dumps(data, ensure_ascii=False)
        self.diskCheckCompleted.emit(res_json)
        return res_json

    # ── Extraction Slots ───────────────────────────────────────────────────────

    @Slot()
    def startDecompression(self):
        """Start parallel decompression of all selected archives."""
        if self._is_extracting or self._is_scanning:
            return

        with self._items_lock:
            selected_items = [i for i in self._items if i.selected and i.status != "done"]

        if not selected_items:
            return

        self._is_extracting = True
        self._extract_cancel_event.clear()
        self.isExtractingChanged.emit()
        self.isBusyChanged.emit()
        self.extractionStarted.emit()

        # Metrics setup
        self._total_bytes_to_extract = sum(i.size for i in selected_items)
        self._extracted_bytes_done = 0
        self._start_time = time.time()

        max_workers = self._max_parallel
        threads = self._threads_per_archive
        delete_after = self._delete_after

        logger.info(
            f"Starting bulk extraction: {len(selected_items)} archive(s) ({_format_bytes(self._total_bytes_to_extract)}) | "
            f"Workers: {max_workers}, Threads/archive: {threads}, Delete after: {delete_after}",
            category="decompressor"
        )

        def _worker():
            success_count = 0
            error_count = 0

            # Thread-safe tracker for active jobs
            active_items: Dict[str, ArchiveItem] = {}
            active_lock = threading.Lock()

            def _update_progress(item: ArchiveItem, pct: float):
                item.progress = pct
                self.itemUpdated.emit(item.item_id, item.status, pct, item.error_message)

                # Compute overall progress
                with self._items_lock:
                    done_b = sum(
                        (i.size if i.status == "done" else (i.size * (i.progress / 100.0) if i.status == "extracting" else 0))
                        for i in selected_items
                    )
                total_b = max(1, self._total_bytes_to_extract)
                overall_pct = min(100.0, (done_b / total_b) * 100.0)

                # Speed and ETA
                elapsed = max(0.1, time.time() - self._start_time)
                speed = done_b / elapsed
                rem_b = max(0, total_b - done_b)
                eta_sec = (rem_b / speed) if speed > 0 else 0

                speed_str = f"{speed / (1024*1024):.1f} MB/s" if speed >= 1024*1024 else f"{speed / 1024:.0f} KB/s"
                if eta_sec > 3600:
                    eta_str = f"{int(eta_sec//3600)}h {int((eta_sec%3600)//60)}m"
                elif eta_sec > 60:
                    eta_str = f"{int(eta_sec//60)}m {int(eta_sec%60)}s"
                else:
                    eta_str = f"{int(eta_sec)}s"

                self.extractionProgress.emit(
                    overall_pct,
                    item.filename,
                    pct,
                    eta_str,
                    speed_str
                )

            def _process_one(item: ArchiveItem):
                if self._extract_cancel_event.is_set():
                    item.status = "skipped"
                    self.itemUpdated.emit(item.item_id, item.status, 0.0, "Cancelled")
                    return False

                item.status = "extracting"
                item.progress = 0.0
                self.itemUpdated.emit(item.item_id, item.status, 0.0, "")
                logger.info(f"Extracting [{item.creator}] {item.filename}...", category="decompressor")

                def _cb(pct: float):
                    _update_progress(item, pct)

                ok, err = self.engine.extract_single_archive(
                    item=item,
                    threads_per_archive=threads,
                    delete_after=delete_after,
                    progress_callback=_cb,
                    cancel_event=self._extract_cancel_event
                )

                if ok:
                    item.status = "done"
                    item.progress = 100.0
                    item.error_message = ""
                    self.itemUpdated.emit(item.item_id, item.status, 100.0, "")
                    logger.success(f"✓ Extracted [{item.creator}] {item.filename} -> {item.target_dir}", category="decompressor")
                    return True
                else:
                    item.status = "error"
                    item.error_message = err
                    self.itemUpdated.emit(item.item_id, item.status, item.progress, err)
                    logger.error(f"✗ Error extracting [{item.creator}] {item.filename}: {err}", category="decompressor")
                    return False

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_process_one, it): it for it in selected_items}
                for f in as_completed(futures):
                    it = futures[f]
                    try:
                        res = f.result()
                        if res:
                            success_count += 1
                        else:
                            error_count += 1
                    except Exception as exc:
                        error_count += 1
                        it.status = "error"
                        it.error_message = str(exc)
                        self.itemUpdated.emit(it.item_id, it.status, it.progress, str(exc))
                        logger.error(f"✗ Exception in [{it.creator}] {it.filename}: {exc}", category="decompressor")

            self._is_extracting = False
            self.isExtractingChanged.emit()
            self.isBusyChanged.emit()
            self.itemsChanged.emit()
            self.selectedStatsChanged.emit()
            self.extractionFinished.emit(success_count, error_count)
            logger.success(
                f"Bulk decompression complete: {success_count} succeeded, {error_count} failed.",
                category="decompressor"
            )

        threading.Thread(target=_worker, daemon=True).start()

    @Slot()
    def cancelDecompression(self):
        """Cancel ongoing extraction jobs immediately."""
        logger.warning("Bulk decompression cancelled by user.", category="decompressor")
        self._extract_cancel_event.set()
        self.engine.cancel_all()

    @Slot()
    def clearFinished(self):
        """Remove completed entries from the list."""
        with self._items_lock:
            self._items = [i for i in self._items if i.status != "done"]
        self.itemsChanged.emit()
        self.selectedStatsChanged.emit()

    @Slot(str)
    def openFolder(self, path: str):
        """Open the enclosing folder in the OS file manager."""
        if not path:
            return
        target = path if os.path.isdir(path) else os.path.dirname(path)
        if os.path.exists(target):
            import subprocess
            if sys.platform == "win32":
                subprocess.Popen(["explorer", os.path.normpath(target)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
