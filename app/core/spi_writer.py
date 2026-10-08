"""
Write dump to SPI flash via libflashrom.
"""

import ctypes
import os
from typing import Callable

from .libflashrom import LibFlashrom, PROGRESS_WRITE


def write_chip(lib: LibFlashrom,
               chip: str,
               file_path: str,
               on_progress: Callable[[int], None],
               on_log: Callable[[str], None],
               on_done: Callable[[bool, str], None]):
    """Write file to chip."""
    if not lib.has_chip():
        on_log("[err] Chip not detected. Press 'Detect' first.")
        on_done(False, "Chip not detected")
        return

    if not os.path.isfile(file_path):
        on_log(f"[err] File not found: {file_path}")
        on_done(False, f"File not found: {file_path}")
        return

    try:
        with open(file_path, "rb") as f:
            data = f.read()
    except Exception as e:
        on_log(f"[err] Could not read file: {e}")
        on_done(False, f"read file: {e}")
        return

    file_size = len(data)
    chip_size = lib.get_size()

    on_log(f"[sys] Chip size: {chip_size} bytes ({chip_size // 1024} KB)")
    on_log(f"[sys] File size: {file_size} bytes ({file_size // 1024} KB)")

    if file_size != chip_size:
        on_log(f"[err] File size ({file_size}) does not match "
               f"chip size ({chip_size})")
        on_done(False, "File size does not match chip size")
        return

    last_pct = {"v": -1}

    def progress_cb(stage, current, total, user_data):
        if stage != PROGRESS_WRITE:
            return
        if total == 0:
            return
        pct = int(current * 100 / total)
        if pct == last_pct["v"]:
            return
        last_pct["v"] = pct
        on_progress(pct)

    lib.set_progress_callback(progress_cb)

    buf = ctypes.create_string_buffer(data, len(data))
    on_log("[sys] Writing...")

    try:
        rc = lib.write(buf)
    except Exception as e:
        on_log(f"[err] Write error: {e}")
        on_done(False, f"write: {e}")
        return

    if rc == 0:
        on_progress(100)
        on_done(True, "Write completed successfully")
    else:
        on_done(False, f"Write error (code {rc})")
