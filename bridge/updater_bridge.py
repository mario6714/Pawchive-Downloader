"""
QML Bridge for Application Updates.
Connects update_service to the QML user interface.
Handles background check on startup, manual checks, download progress,
and applying updates with restart.
"""

import threading
from PySide6.QtCore import QObject, Signal, Slot, Property, QTimer
from core.logger import logger
from services.update_service import (
    is_compiled,
    check_for_updates,
    UpdateDownloader,
    apply_update_and_restart,
    get_local_version_info
)


class UpdaterBridge(QObject):
    isCheckingChanged = Signal()
    updateAvailableChanged = Signal()
    isDownloadingChanged = Signal()
    isReadyChanged = Signal()
    progressChanged = Signal()
    statusChanged = Signal()
    infoChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_checking = False
        self._update_available = False
        self._is_downloading = False
        self._is_ready = False
        self._progress = 0.0
        self._speed_str = "--"
        self._status_message = "Up to date"

        local_info = get_local_version_info()
        self._current_version = local_info.get("version", "") if is_compiled() else (local_info.get("short_commit", "") or "source")
        self._latest_version = ""
        self._commit_message = ""
        self._release_date = ""
        self._release_url = ""
        self._update_info = {}

        self._downloader: UpdateDownloader = None

        # Schedule quiet startup check after 3.5 seconds
        QTimer.singleShot(3500, self._startup_check)

    def _startup_check(self):
        """Runs initial background check quietly."""
        self.checkForUpdates(silent=True)

    # ── Properties ────────────────────────────────────────────────────────────

    @Property(bool, notify=isCheckingChanged)
    def isChecking(self) -> bool:
        return self._is_checking

    @Property(bool, notify=updateAvailableChanged)
    def updateAvailable(self) -> bool:
        return self._update_available

    @Property(bool, notify=isDownloadingChanged)
    def isDownloading(self) -> bool:
        return self._is_downloading

    @Property(bool, notify=isReadyChanged)
    def isReady(self) -> bool:
        return self._is_ready

    @Property(float, notify=progressChanged)
    def downloadProgress(self) -> float:
        return self._progress

    @Property(str, notify=progressChanged)
    def downloadSpeed(self) -> str:
        return self._speed_str

    @Property(str, notify=statusChanged)
    def statusMessage(self) -> str:
        return self._status_message

    @Property(str, notify=infoChanged)
    def currentVersion(self) -> str:
        return self._current_version

    @Property(str, notify=infoChanged)
    def latestVersion(self) -> str:
        return self._latest_version

    @Property(str, notify=infoChanged)
    def commitMessage(self) -> str:
        return self._commit_message

    @Property(str, notify=infoChanged)
    def releaseDate(self) -> str:
        return self._release_date

    @Property(str, notify=infoChanged)
    def releaseUrl(self) -> str:
        return self._release_url

    @Property(bool, constant=True)
    def isCompiled(self) -> bool:
        return is_compiled()

    # ── Slots ─────────────────────────────────────────────────────────────────

    @Slot(bool)
    def checkForUpdates(self, silent: bool = False):
        """Check for updates asynchronously."""
        if self._is_checking or self._is_downloading:
            return

        self._is_checking = True
        self.isCheckingChanged.emit()
        if not silent:
            self._status_message = "Checking for updates..."
            self.statusChanged.emit()

        def _worker():
            try:
                res = check_for_updates(timeout=8)
                self._update_info = res
                self._is_checking = False

                if res.get("update_available"):
                    self._update_available = True
                    self._latest_version = res.get("remote_version", "") or res.get("remote_commit", "")
                    self._commit_message = res.get("commit_message", "") or res.get("release_notes", "")
                    self._release_date = res.get("published_at", "")[:10]
                    self._release_url = res.get("release_url", "")
                    self._status_message = f"New version available: {self._latest_version}"
                    logger.info(f"✨ Update found on GitHub: {self._latest_version} ('{self._commit_message}')", category="system")
                else:
                    if not silent:
                        if res.get("error"):
                            self._status_message = f"Check failed: {res['error']}"
                        else:
                            self._status_message = "You are running the latest version."
                            logger.info("Application is up to date.", category="system")

                self.isCheckingChanged.emit()
                self.updateAvailableChanged.emit()
                self.infoChanged.emit()
                self.statusChanged.emit()

            except Exception as e:
                self._is_checking = False
                self.isCheckingChanged.emit()
                if not silent:
                    self._status_message = f"Error: {e}"
                    self.statusChanged.emit()

        threading.Thread(target=_worker, daemon=True).start()

    @Slot()
    def startDownload(self):
        """Handoff update to standalone companion updater.exe and cleanly exit main app."""
        from services.update_service import launch_external_updater
        logger.info("Launching standalone updater.exe and closing application...", category="system")
        launch_external_updater(self._update_info)

        def on_prog(pct, msg):
            self._progress = pct
            self._status_message = msg
            self._speed_str = self._downloader.speed_str
            self.progressChanged.emit()
            self.statusChanged.emit()

        def on_done(success, err):
            self._is_downloading = False
            self.isDownloadingChanged.emit()
            if success:
                self._is_ready = True
                self._progress = 1.0
                self._status_message = "Update ready to install!"
                self.isReadyChanged.emit()
                self.progressChanged.emit()
                self.statusChanged.emit()
                logger.info("Update package downloaded and staged successfully.", category="system")
            else:
                self._status_message = f"Download failed: {err}"
                self.statusChanged.emit()
                logger.error(f"Update download failed: {err}", category="system")

        self._downloader.start_download(on_progress=on_prog, on_finished=on_done)

    @Slot()
    def cancelDownload(self):
        """Cancel ongoing update download."""
        if self._downloader and self._is_downloading:
            self._downloader.cancel()
            self._is_downloading = False
            self._status_message = "Download cancelled."
            self.isDownloadingChanged.emit()
            self.statusChanged.emit()

    @Slot()
    def applyAndRestart(self):
        """Apply staged update and restart the application."""
        from services.update_service import launch_external_updater
        logger.info("Launching standalone updater.exe and closing application...", category="system")
        launch_external_updater(self._update_info)

    @Slot()
    def dismissUpdate(self):
        """Hide update prompt for current session."""
        self._update_available = False
        self.updateAvailableChanged.emit()
