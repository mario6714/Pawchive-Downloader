"""
Pawchive Downloader - Standalone Companion Updater.
Packaged as a lightweight onefile GUI application (console hidden).
Handles downloading, staging, zero-lock file synchronization, and application relaunch.
"""

import os
import sys
import time
import json
import shutil
import zipfile
import argparse
import subprocess
import threading
import urllib.request
from typing import Optional

# GUI: Tkinter (standard library, zero external DLL dependency)
import tkinter as tk
from tkinter import ttk

# Files and folders that must NEVER be overwritten during an update
PROTECTED_DIRS = {"config", "downloads", "temp", "logs", "venv", ".venv", "__pycache__", ".git"}
PROTECTED_FILES = {"settings.json", "watchlist.json", "known.txt", "cookies.txt"}


def is_pid_running(pid: int) -> bool:
    """Check if process with given PID is still active on Windows."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if not handle:
                return False
            STILL_ACTIVE = 259
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return code.value == STILL_ACTIVE
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


class UpdaterApp:
    def __init__(self, root: tk.Tk, target_dir: str, pid: int, download_url: str, version: str):
        self.root = root
        self.target_dir = os.path.abspath(target_dir)
        self.pid = pid
        self.download_url = download_url
        self.version = version or "Latest"
        self._cancel_requested = False

        self._setup_window()
        self._setup_styles()
        self._create_widgets()

        # Start background update worker
        threading.Thread(target=self._run_update_pipeline, daemon=True).start()

    def _setup_window(self):
        self.root.title("Pawchive Downloader Updater")
        self.root.geometry("480x280")
        self.root.resizable(False, False)
        self.root.configure(bg="#121214")

        # Center on screen
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"+{x}+{y}")

        # Set application icon if exists
        icon_path = os.path.join(self.target_dir, "assets", "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

    def _setup_styles(self):
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")

        # Custom purple progressbar
        self.style.configure(
            "Purple.Horizontal.TProgressbar",
            troughcolor="#1e1e24",
            background="#a855f7",
            darkcolor="#9333ea",
            lightcolor="#c084fc",
            bordercolor="#1e1e24",
            thickness=10
        )

    def _create_widgets(self):
        # Outer Card
        card = tk.Frame(self.root, bg="#18181b", bd=1, relief="flat", highlightbackground="#27272a", highlightthickness=1)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # Header with Logo & Title
        header_frame = tk.Frame(card, bg="#18181b")
        header_frame.pack(fill="x", padx=20, pady=(18, 10))

        title_label = tk.Label(
            header_frame,
            text="Pawchive Downloader",
            font=("Segoe UI", 14, "bold"),
            fg="#f4f4f5",
            bg="#18181b"
        )
        title_label.pack(side="left")

        self.ver_badge = tk.Label(
            header_frame,
            text=f"Updating to {self.version}",
            font=("Segoe UI", 9, "bold"),
            fg="#a855f7",
            bg="#27272a",
            padx=8,
            pady=2
        )
        self.ver_badge.pack(side="right")

        # Status text
        self.status_label = tk.Label(
            card,
            text="Preparing update...",
            font=("Segoe UI", 10),
            fg="#e4e4e7",
            bg="#18181b",
            anchor="w"
        )
        self.status_label.pack(fill="x", padx=20, pady=(14, 6))

        # Progress bar
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            card,
            variable=self.progress_var,
            maximum=100.0,
            style="Purple.Horizontal.TProgressbar"
        )
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 6))

        # Sub-status / Speed details
        self.detail_label = tk.Label(
            card,
            text="Please wait while the update is applied...",
            font=("Segoe UI", 8),
            fg="#71717a",
            bg="#18181b",
            anchor="w"
        )
        self.detail_label.pack(fill="x", padx=20, pady=(0, 16))

        # Footer button area
        btn_frame = tk.Frame(card, bg="#18181b")
        btn_frame.pack(fill="x", padx=20, pady=(0, 12))

        self.cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            font=("Segoe UI", 9),
            fg="#a1a1aa",
            bg="#27272a",
            activebackground="#3f3f46",
            activeforeground="#f4f4f5",
            bd=0,
            padx=14,
            pady=4,
            cursor="hand2",
            command=self._on_cancel
        )
        self.cancel_btn.pack(side="right")

    def _set_status(self, status: str, detail: str = "", progress: Optional[float] = None):
        def _update():
            self.status_label.config(text=status)
            if detail is not None:
                self.detail_label.config(text=detail)
            if progress is not None:
                self.progress_var.set(progress)
        self.root.after(0, _update)

    def _on_cancel(self):
        self._cancel_requested = True
        self._set_status("Cancelling update...", "Cleaning up temporary files...")
        self.root.after(1000, self.root.destroy)

    def _run_update_pipeline(self):
        try:
            # 1. Wait for Pawchive Downloader to completely terminate
            if self.pid > 0:
                self._set_status("Closing Pawchive Downloader...", "Waiting for process to unlock files...")
                start_wait = time.time()
                while is_pid_running(self.pid):
                    if self._cancel_requested:
                        return
                    if time.time() - start_wait > 12:
                        break
                    time.sleep(0.3)

            time.sleep(0.5)  # Buffer for Windows OS file handle release

            # 2. Prepare directories in %TEMP%
            temp_base = os.environ.get("TEMP", os.path.expanduser("~"))
            updater_work_dir = os.path.join(temp_base, f"pawchive_update_{int(time.time())}")
            zip_dest = os.path.join(updater_work_dir, "update.zip")
            staging_dir = os.path.join(updater_work_dir, "staging")
            os.makedirs(staging_dir, exist_ok=True)

            # 3. Download Release ZIP
            self._set_status("Connecting to GitHub...", "Resolving release package...", progress=5.0)
            req = urllib.request.Request(self.download_url, headers={"User-Agent": "Pawchive-Updater/1.0"})

            with urllib.request.urlopen(req, timeout=30) as resp:
                total_size = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                start_t = time.time()
                last_ui_t = start_t

                with open(zip_dest, "wb") as out_f:
                    while True:
                        if self._cancel_requested:
                            shutil.rmtree(updater_work_dir, ignore_errors=True)
                            return
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        downloaded += len(chunk)

                        now = time.time()
                        if now - last_ui_t >= 0.25 or downloaded == total_size:
                            last_ui_t = now
                            pct = (downloaded / total_size * 100) if total_size > 0 else 50.0
                            elapsed = max(0.001, now - start_t)
                            speed_mb = (downloaded / elapsed) / (1024 * 1024)
                            mb_done = downloaded / (1024 * 1024)
                            mb_total = total_size / (1024 * 1024)

                            rem_sec = int((total_size - downloaded) / max(1, downloaded / elapsed)) if total_size > 0 else 0
                            eta_str = f"ETA: {rem_sec}s" if rem_sec < 120 else f"ETA: {rem_sec // 60}m {rem_sec % 60}s"

                            status = f"Downloading update ({int(pct)}%)..."
                            detail = f"{mb_done:.1f} MB / {mb_total:.1f} MB • {speed_mb:.1f} MB/s • {eta_str}"
                            # Scale download progress 5% -> 80%
                            self._set_status(status, detail, progress=5.0 + (pct * 0.75))

            # 4. Extract Package
            self.root.after(0, lambda: self.cancel_btn.config(state="disabled"))
            self._set_status("Extracting update package...", "Verifying files...", progress=82.0)

            with zipfile.ZipFile(zip_dest, "r") as zf:
                zf.extractall(staging_dir)

            # Locate root directory inside zip if nested
            stage_root = staging_dir
            entries = [os.path.join(staging_dir, e) for e in os.listdir(staging_dir)]
            if len(entries) == 1 and os.path.isdir(entries[0]):
                stage_root = entries[0]

            # 5. Synchronize files into target directory
            self._set_status("Installing update...", "Replacing application binaries...", progress=90.0)

            copied_count = 0
            for root_d, dirs, files in os.walk(stage_root):
                rel = os.path.relpath(root_d, stage_root)
                first = rel.split(os.sep)[0] if rel != "." else ""

                if first.lower() in PROTECTED_DIRS:
                    dirs[:] = []
                    continue

                dest_folder = self.target_dir if rel == "." else os.path.join(self.target_dir, rel)
                os.makedirs(dest_folder, exist_ok=True)

                for file_name in files:
                    if file_name.lower() in PROTECTED_FILES:
                        continue
                    s_file = os.path.join(root_d, file_name)
                    d_file = os.path.join(dest_folder, file_name)
                    try:
                        shutil.copy2(s_file, d_file)
                        copied_count += 1
                    except Exception as e:
                        # Retry once after short sleep if locked
                        time.sleep(0.5)
                        try:
                            shutil.copy2(s_file, d_file)
                            copied_count += 1
                        except Exception:
                            pass

            self._set_status("Finalizing update...", f"Updated {copied_count} files successfully.", progress=98.0)
            time.sleep(0.5)

            # 6. Clean up temporary files
            shutil.rmtree(updater_work_dir, ignore_errors=True)

            # 7. Relaunch Application
            self._set_status("Update complete!", "Relaunching Pawchive Downloader...", progress=100.0)
            time.sleep(0.8)

            exe_path = os.path.join(self.target_dir, "Pawchive Downloader.exe")
            if not os.path.exists(exe_path):
                # Fallback search
                for f in os.listdir(self.target_dir):
                    if f.lower().endswith(".exe") and "updater" not in f.lower():
                        exe_path = os.path.join(self.target_dir, f)
                        break

            if os.path.exists(exe_path):
                subprocess.Popen([exe_path], cwd=self.target_dir)

            self.root.after(500, self.root.destroy)

        except Exception as err:
            self._set_status("Update Failed", f"Error: {err}", progress=0.0)
            self.root.after(0, lambda: self.cancel_btn.config(text="Close", state="normal", command=self.root.destroy))


def main():
    parser = argparse.ArgumentParser(description="Pawchive Downloader Standalone Companion Updater")
    parser.add_argument("--target-dir", default="", help="Installation root of Pawchive Downloader")
    parser.add_argument("--pid", type=int, default=0, help="PID of the running main app to wait for")
    parser.add_argument("--download-url", default="", help="Direct download URL for the update zip")
    parser.add_argument("--version", default="", help="Target version string to display")
    parser.add_argument("--temp-runner", action="store_true", help="Internal flag: running from temp location")

    args = parser.parse_args()

    target_dir = args.target_dir
    if not target_dir:
        if getattr(sys, "frozen", False):
            target_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            target_dir = os.path.dirname(os.path.abspath(__file__))

    download_url = args.download_url
    version = args.version
    if not download_url:
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/whyamihere773/Pawchive-Downloader/releases/latest",
                headers={"User-Agent": "Pawchive-Updater/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not version:
                    version = data.get("tag_name", "")
                for asset in data.get("assets", []):
                    name = asset.get("name", "").lower()
                    if name.endswith(".zip"):
                        download_url = asset.get("browser_download_url", "")
                        break
        except Exception:
            pass

    if not download_url:
        print("❌ Error: No download package URL provided and could not query GitHub releases.")
        sys.exit(1)

    # Self-relocation:
    # If running from inside target_dir as a compiled exe, copy self to %TEMP%
    # so target_dir/updater.exe itself is not locked and can be cleanly updated!
    if getattr(sys, "frozen", False) and not args.temp_runner:
        my_exe = os.path.abspath(sys.executable)
        temp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
        temp_updater = os.path.join(temp_dir, f"pawchive_updater_run_{int(time.time())}.exe")
        try:
            shutil.copy2(my_exe, temp_updater)
            cmd = [
                temp_updater,
                "--target-dir", target_dir,
                "--pid", str(args.pid),
                "--download-url", download_url,
                "--version", version,
                "--temp-runner"
            ]
            subprocess.Popen(cmd)
            sys.exit(0)
        except Exception:
            pass  # Fall back to running in-place

    root = tk.Tk()
    app = UpdaterApp(
        root=root,
        target_dir=target_dir,
        pid=args.pid,
        download_url=download_url,
        version=version
    )
    root.mainloop()


if __name__ == "__main__":
    main()
