"""
USB device detection for CH341-family programmers.

Scans USB bus for devices with WCH vendor ID (0x1a86) and maps known
Product IDs to human-readable names.

Also supports user-defined PID (from config) for unknown revisions.
"""

import subprocess
from typing import List, Dict, Optional


# WCH vendor ID (all CH340/CH341 chips)
WCH_VID = 0x1A86

# Known Product IDs
KNOWN_PIDS: Dict[int, str] = {
    0x5512: "CH341A (SPI/I2C)",
    0x5523: "CH341A (UART) / CH341B",
    0x7523: "CH340 (UART)",
    0x5584: "CH341 (Parallel)",
}


class UsbDevice:
    """Represents a single USB device with WCH vendor ID."""

    def __init__(self, vid: int, pid: int):
        self.vid = vid
        self.pid = pid

    @property
    def name(self) -> str:
        return KNOWN_PIDS.get(self.pid, "Unknown WCH device")

    @property
    def known(self) -> bool:
        return self.pid in KNOWN_PIDS

    @property
    def is_spi(self) -> bool:
        return self.pid == 0x5512

    @property
    def is_uart(self) -> bool:
        return self.pid in (0x5523, 0x7523)

    def __repr__(self):
        return (f"UsbDevice(vid=0x{self.vid:04x}, "
                f"pid=0x{self.pid:04x}, name={self.name})")


def scan_wch_devices() -> List[UsbDevice]:
    """
    Scan USB bus for all WCH devices (VID 0x1a86).

    Uses system_profiler (macOS built-in).
    Parses by device blocks (VID/PID order does not matter).
    """
    try:
        out = subprocess.run(
            ["system_profiler", "SPUSBDataType"],
            capture_output=True, text=True, timeout=10
        )
        text = out.stdout
    except Exception:
        return []

    devices = []
    lines = text.splitlines()

    current_vid = None
    current_pid = None

    def flush():
        """If both VID and PID collected — check and add device."""
        nonlocal current_vid, current_pid
        if current_vid == WCH_VID and current_pid is not None:
            devices.append(UsbDevice(WCH_VID, current_pid))

    for line in lines:
        stripped = line.strip()

        if stripped.endswith(":") and not stripped.startswith(
                ("Product ID", "Vendor ID", "Version", "Speed",
                 "Location ID", "Current", "Extra", "Manufacturer",
                 "Serial Number", "bcdDevice")):
            flush()
            current_vid = None
            current_pid = None

        if stripped.startswith("Vendor ID:"):
            try:
                vid_str = stripped.split("0x")[1].split()[0]
                current_vid = int(vid_str, 16)
            except Exception:
                current_vid = None
        elif stripped.startswith("Product ID:"):
            try:
                pid_str = stripped.split("0x")[1].split()[0]
                current_pid = int(pid_str, 16)
            except Exception:
                current_pid = None

    # Last block
    flush()

    return devices


def find_programmer() -> Optional[UsbDevice]:
    """
    Return the first WCH device that looks like a programmer (SPI or UART).
    Returns None if not found.
    """
    devices = scan_wch_devices()
    for d in devices:
        if d.is_spi or d.is_uart:
            return d
    return None


def describe_devices() -> str:
    """Return human-readable description of all WCH devices found."""
    devices = scan_wch_devices()
    if not devices:
        return "No WCH devices found"

    lines = []
    for d in devices:
        mark = "OK" if d.known else "?"
        lines.append(f"[{mark}] 0x{d.vid:04x}:0x{d.pid:04x} - {d.name}")
    return "\n".join(lines)
