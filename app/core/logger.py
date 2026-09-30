"""
File logger with timestamps and rotation.

Path: ~/Library/Logs/SPI-UART-Tool/app.log
Rotation: on startup, if file > MAX_SIZE (5 MB) — delete it.
"""

import os
import time


LOG_DIR = os.path.expanduser("~/Library/Logs/SPI-UART-Tool")
LOG_PATH = os.path.join(LOG_DIR, "app.log")
MAX_SIZE = 5 * 1024 * 1024  # 5 MB


class Logger:
    """Simple file logger."""

    def __init__(self):
        self.path = LOG_PATH
        self._enabled = True
        self._rotate_if_needed()

    # ---------- Public ----------
    def log(self, msg: str):
        """Write a line with timestamp."""
        if not self._enabled:
            return
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}\n"
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            # not critical if the write fails
            pass

    def get_size(self) -> int:
        """Return log file size in bytes (0 if missing)."""
        try:
            return os.path.getsize(self.path)
        except OSError:
            return 0

    def get_size_human(self) -> str:
        """Return size in human-readable form."""
        size = self.get_size()
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.2f} MB"

    def clear(self):
        """Delete log file."""
        try:
            if os.path.isfile(self.path):
                os.remove(self.path)
        except Exception:
            pass

    def open_in_default(self):
        """Open log file with the default macOS app."""
        import subprocess
        if not os.path.isfile(self.path):
            # create empty file so there is something to open
            self.log("[sys] Log file created")
        try:
            subprocess.Popen(["open", self.path])
        except Exception:
            pass

    # ---------- Internal ----------
    def _rotate_if_needed(self):
        """If file is larger than MAX_SIZE — delete it on startup."""
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            if os.path.isfile(self.path) and os.path.getsize(self.path) > MAX_SIZE:
                os.remove(self.path)
        except Exception:
            pass
