"""
Erase SPI flash via libflashrom.
"""

from typing import Callable

from .libflashrom import LibFlashrom


def erase_chip(lib: LibFlashrom,
               chip: str,
               on_progress: Callable[[int], None],
               on_log: Callable[[str], None],
               on_done: Callable[[bool, str], None]):
    """Erase whole chip."""
    if not lib.has_chip():
        on_log("[err] Chip not detected. Press 'Detect' first.")
        on_done(False, "Chip not detected")
        return

    chip_size = lib.get_size()
    on_log(f"[sys] Chip size: {chip_size} bytes ({chip_size // 1024} KB)")

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

    on_log("[sys] Erasing...")

    try:
        rc = lib.erase()
    except Exception as e:
        on_log(f"[err] Erase error: {e}")
        on_done(False, f"erase: {e}")
        return

    if rc == 0:
        on_progress(100)
        on_done(True, "Chip erased successfully")
    else:
        on_done(False, f"Erase error (code {rc})")
