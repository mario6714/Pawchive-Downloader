"""
In-App GitHub Updater Service.
Supports running both from source (main.py) and compiled (.exe).
Compares commit SHA for source or release tag for compiled versions,
downloads the latest zip from GitHub, stages the files, and performs
a safe restart hand-off.
"""

import os
import sys
import json
import shutil
import zipfile
import urllib.request
import subprocess
import threading
import time
from typing import Optional, Dict, Any, Callable

GITHUB_OWNER = "whyamihere773"
GITHUB_REPO = "Pawchive-Downloader"
GITHUB_BRANCH = "main"

USER_AGENT = "Pawchive-Downloader-Updater/1.0"


def is_compiled() -> bool:
    """Return True if running as a compiled standalone executable (PyInstaller/Nuitka/etc)."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS") or getattr(sys, "frozen", False)


def get_app_dir() -> str:
    """Get the root directory of the application."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # When running from source, app dir is the project root (parent of services/)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_local_version_info() -> Dict[str, str]:
    """Retrieve currently installed version or commit SHA."""
    app_dir = get_app_dir()
    version_file = os.path.join(app_dir, "version.json")
    if os.path.exists(version_file):
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Fallback to local git if running from source with .git
    git_dir = os.path.join(app_dir, ".git")
    if os.path.exists(git_dir):
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=app_dir,
                capture_output=True,
                text=True,
                timeout=3
            )
            if res.returncode == 0 and res.stdout.strip():
                return {
                    "commit": res.stdout.strip(),
                    "short_commit": res.stdout.strip()[:7],
                    "version": "source-dev",
                    "date": ""
                }
        except Exception:
            pass

    return {
        "commit": "",
        "short_commit": "current",
        "version": "1.0.0",
        "date": ""
    }


def check_for_updates(timeout: int = 8) -> Dict[str, Any]:
    """
    Check GitHub API for updates.
    - If running from source: checks latest commit on default branch.
    - If running as compiled: checks latest release.
    """
    local_info = get_local_version_info()
    compiled = is_compiled()

    if compiled:
        # Check GitHub Releases
        api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {
                "update_available": False,
                "error": f"Could not check releases: {e}",
                "compiled": True,
                "local_version": local_info.get("version", "1.0.0")
            }

        remote_tag = data.get("tag_name", "").strip().lstrip("v")
        local_ver = local_info.get("version", "").strip().lstrip("v")
        body = data.get("body", "")
        release_url = data.get("html_url", "")

        # Look for zip or exe asset
        download_url = ""
        for asset in data.get("assets", []):
            name = asset.get("name", "").lower()
            if name.endswith(".zip") or name.endswith(".exe"):
                download_url = asset.get("browser_download_url", "")
                break

        update_available = bool(remote_tag and remote_tag != local_ver)
        return {
            "update_available": update_available,
            "compiled": True,
            "local_version": local_info.get("version", "1.0.0"),
            "remote_version": data.get("tag_name", ""),
            "commit_message": data.get("name", "") or data.get("tag_name", ""),
            "release_notes": body,
            "download_url": download_url,
            "release_url": release_url,
            "published_at": data.get("published_at", "")
        }

    else:
        # Running from source: check commits on main branch
        api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits/{GITHUB_BRANCH}"
        req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {
                "update_available": False,
                "error": f"Could not check commits: {e}",
                "compiled": False,
                "local_commit": local_info.get("short_commit", "")
            }

        remote_sha = data.get("sha", "").strip()
        remote_short = remote_sha[:7] if remote_sha else ""
        commit_msg = data.get("commit", {}).get("message", "").split("\n")[0]
        commit_date = data.get("commit", {}).get("author", {}).get("date", "")
        download_url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"

        local_sha = local_info.get("commit", "").strip()
        update_available = bool(remote_sha and remote_sha != local_sha)

        return {
            "update_available": update_available,
            "compiled": False,
            "local_commit": local_info.get("short_commit", "") or local_sha[:7],
            "remote_commit": remote_short,
            "full_remote_sha": remote_sha,
            "commit_message": commit_msg,
            "download_url": download_url,
            "published_at": commit_date
        }


class UpdateDownloader:
    """Handles downloading and staging the update zip in a background thread."""

    def __init__(self, download_url: str, update_info: Dict[str, Any]):
        self.download_url = download_url
        self.update_info = update_info
        self.app_dir = get_app_dir()
        self.temp_dir = os.path.join(self.app_dir, "temp", "update")
        self.zip_path = os.path.join(self.temp_dir, "update.zip")
        self.staging_dir = os.path.join(self.temp_dir, "staging")

        self.is_downloading = False
        self.progress = 0.0
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.speed_str = "--"
        self.status_text = "Idle"
        self.error_message = ""
        self.is_ready = False

        self._cancel_event = threading.Event()

    def start_download(
        self,
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_finished: Optional[Callable[[bool, str], None]] = None
    ):
        """Starts asynchronous download and staging."""
        self._cancel_event.clear()
        self.is_downloading = True
        self.error_message = ""
        self.is_ready = False

        def _worker():
            try:
                os.makedirs(self.temp_dir, exist_ok=True)
                if os.path.exists(self.staging_dir):
                    shutil.rmtree(self.staging_dir, ignore_errors=True)
                os.makedirs(self.staging_dir, exist_ok=True)

                self.status_text = "Connecting to GitHub..."
                if on_progress:
                    on_progress(0.05, self.status_text)

                req = urllib.request.Request(self.download_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    total = int(resp.headers.get("Content-Length", 0))
                    self.total_bytes = total
                    downloaded = 0
                    start_time = time.time()
                    last_time = start_time

                    with open(self.zip_path, "wb") as out_f:
                        while True:
                            if self._cancel_event.is_set():
                                self.status_text = "Cancelled"
                                self.is_downloading = False
                                return

                            chunk = resp.read(64 * 1024)
                            if not chunk:
                                break
                            out_f.write(chunk)
                            downloaded += len(chunk)
                            self.downloaded_bytes = downloaded

                            now = time.time()
                            if now - last_time >= 0.25 or downloaded == total:
                                last_time = now
                                pct = (downloaded / total) if total > 0 else 0.5
                                elapsed = max(0.001, now - start_time)
                                speed_bps = downloaded / elapsed
                                speed_mb = speed_bps / (1024 * 1024)
                                self.speed_str = f"{speed_mb:.1f} MB/s"
                                self.progress = pct
                                self.status_text = f"Downloading: {int(pct * 100)}% ({self.speed_str})"
                                if on_progress:
                                    on_progress(pct, self.status_text)

                self.status_text = "Extracting & verifying update package..."
                if on_progress:
                    on_progress(0.95, self.status_text)

                # Extract zip to staging
                with zipfile.ZipFile(self.zip_path, "r") as z:
                    z.extractall(self.staging_dir)

                # If extracted folder has a single root directory (e.g. Pawchive-Downloader-main/),
                # locate that inner root
                entries = os.listdir(self.staging_dir)
                actual_stage_root = self.staging_dir
                if len(entries) == 1 and os.path.isdir(os.path.join(self.staging_dir, entries[0])):
                    actual_stage_root = os.path.join(self.staging_dir, entries[0])

                self.staging_root = actual_stage_root
                self.is_ready = True
                self.is_downloading = False
                self.status_text = "Update Ready to Install!"
                if on_finished:
                    on_finished(True, "")

            except Exception as e:
                self.is_downloading = False
                self.error_message = str(e)
                self.status_text = f"Error: {e}"
                if on_finished:
                    on_finished(False, str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def cancel(self):
        self._cancel_event.set()


def apply_update_and_restart(staging_root: str, update_info: Dict[str, Any]):
    """
    Spawns an out-of-process updater to replace application files and restart,
    then cleanly terminates the running application.
    """
    app_dir = get_app_dir()
    current_pid = os.getpid()
    compiled = is_compiled()

    sha = update_info.get("full_remote_sha", "") or update_info.get("remote_commit", "")
    version = update_info.get("remote_version", "") or "source-update"

    if compiled and sys.platform == "win32":
        exe_path = sys.executable
        temp_dir = os.environ.get("TEMP", os.path.join(app_dir, "temp"))
        bat_path = os.path.join(temp_dir, f"pawchive_updater_{current_pid}.bat")
        log_path = os.path.join(temp_dir, f"pawchive_updater_{current_pid}.log")

        bat_content = f"""@echo off
setlocal enabledelayedexpansion

set "PID={current_pid}"
set "TARGET_DIR={app_dir}"
set "STAGING_DIR={staging_root}"
set "EXE_PATH={exe_path}"
set "LOG_FILE={log_path}"

echo [%DATE% %TIME%] Updater started. Waiting for PID %PID% to exit... > "%LOG_FILE%"

:WAIT_PID
tasklist /fi "PID eq %PID%" 2>NUL | findstr /i "%PID%" >NUL
if not errorlevel 1 (
    timeout /t 1 /nobreak >NUL
    goto WAIT_PID
)

echo [%DATE% %TIME%] Process %PID% exited. Waiting 1s for file locks to release... >> "%LOG_FILE%"
timeout /t 1 /nobreak >NUL

echo [%DATE% %TIME%] Copying files from "%STAGING_DIR%" to "%TARGET_DIR%"... >> "%LOG_FILE%"
robocopy "%STAGING_DIR%" "%TARGET_DIR%" /E /XD temp logs .git downloads /XF settings.json watchlist.json Known.txt cookies.txt /R:5 /W:1 /NP /NDL /NFL >> "%LOG_FILE%" 2>&1

if %ERRORLEVEL% GEQ 8 (
    echo [%DATE% %TIME%] Robocopy error %ERRORLEVEL%, falling back to xcopy... >> "%LOG_FILE%"
    xcopy "%STAGING_DIR%\\*" "%TARGET_DIR%\\" /S /E /Y /I /Q >> "%LOG_FILE%" 2>&1
)

echo [%DATE% %TIME%] Cleaning up staging directory... >> "%LOG_FILE%"
rmdir /s /q "%STAGING_DIR%" 2>NUL

echo [%DATE% %TIME%] Launching "%EXE_PATH%"... >> "%LOG_FILE%"
cd /d "%TARGET_DIR%"
start "" "%EXE_PATH%"

echo [%DATE% %TIME%] Updater completed successfully. >> "%LOG_FILE%"
(goto) 2>nul & del "%~f0"
"""
        with open(bat_path, "w", encoding="ascii", errors="replace") as f:
            f.write(bat_content)

        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(["cmd.exe", "/c", bat_path], creationflags=creationflags, close_fds=True)
        # Force immediate hard process exit so file locks on exe and _internal are released instantly
        os._exit(0)

    else:
        # Running from source (or non-Windows)
        helper_script = os.path.join(os.path.dirname(__file__), "updater_helper.py")
        python_exe = sys.executable

        args = [
            python_exe,
            helper_script,
            "--target-dir", app_dir,
            "--staging-dir", staging_root,
            "--pid", str(current_pid),
            "--commit-sha", sha,
            "--version-str", version,
            "--is-compiled", "0"
        ]

        if sys.platform == "win32":
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            subprocess.Popen(args, creationflags=creationflags, close_fds=True)
        else:
            subprocess.Popen(args, start_new_session=True, close_fds=True)

        os._exit(0)
