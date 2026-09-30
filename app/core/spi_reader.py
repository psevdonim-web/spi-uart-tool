"""
Read SPI flash dump via libflashrom.
"""

import ctypes
import hashlib
import os
from typing import Callable, Optional

from .libflashrom import LibFlashrom


def sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_chip(lib: LibFlashrom,
              chip: str,
              out_path: str,
              on_progress: Callable[[int], None],
              on_log: Callable[[str], None],
              on_done: Callable[[bool, str, Optional[str]], None]):
    """Read chip into out_path."""
    if not lib.has_chip():
        on_log("[err] Chip not detected. Press 'Detect' first.")
        on_done(False, "Chip not detected", None)
        return

    size = lib.get_size()
    on_log(f"[sys] Chip size: {size} bytes ({size // 1024} KB)")

    last_pct = {"v": -1}

    def progress_cb(stage, current, total, user_data):
        if total == 0:
            return
        pct = int(current * 100 / total)
        if pct == last_pct["v"]:
            return
        last_pct["v"] = pct
        on_progress(pct)

    lib.set_progress_callback(progress_cb)

    buf = ctypes.create_string_buffer(size)
    on_log("[sys] Reading...")

    try:
        rc = lib.read(buf)
    except Exception as e:
        on_log(f"[err] Read error: {e}")
        on_done(False, f"read: {e}", None)
        return

    if rc != 0:
        on_log(f"[err] flashrom_image_read returned {rc}")
        on_done(False, f"Read error (code {rc})", None)
        return

    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(buf.raw)
    except Exception as e:
        on_log(f"[err] Could not save: {e}")
        on_done(False, f"save: {e}", None)
        return

    try:
        sha = sha256_of_file(out_path)
    except Exception as e:
        on_log(f"[err] Could not compute hash: {e}")
        on_done(False, f"sha256: {e}", None)
        return

    on_progress(100)
    on_done(True, f"Read {size // 1024} KB -> {out_path}", sha)
