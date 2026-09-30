"""
Chip detection via libflashrom.
"""

from dataclasses import dataclass
from typing import Optional

from .libflashrom import LibFlashrom


@dataclass
class DetectResult:
    ok: bool
    chip: Optional[str]
    size_kb: Optional[int]
    error: Optional[str]


def detect_chip(lib: LibFlashrom, chip_name: str = None) -> DetectResult:
    """
    Detect chip.
    chip_name=None — auto-detect.
    """
    try:
        real_name = lib.probe_chip(chip_name=chip_name)
    except Exception as e:
        return DetectResult(
            ok=False, chip=None, size_kb=None,
            error=f"Chip not found: {e}"
        )

    try:
        size_bytes = lib.get_size()
        size_kb = size_bytes // 1024
    except Exception as e:
        return DetectResult(
            ok=False, chip=None, size_kb=None,
            error=f"Could not get chip size: {e}"
        )

    return DetectResult(
        ok=True,
        chip=real_name or "auto",
        size_kb=size_kb,
        error=None,
    )
