"""
Build configuration for py2app.
Creates a standalone .app bundle for SPI & UART Tool.
"""

import os
from setuptools import setup


APP = ["main.py"]


def collect_dir(src_dir, target_rel):
    """Collect all files from src_dir for data_files."""
    result = []
    for root, dirs, files in os.walk(src_dir):
        if not files:
            continue
        rel = os.path.relpath(root, src_dir)
        target = os.path.join(target_rel, rel) if rel != "." else target_rel
        file_paths = [os.path.join(root, f) for f in files]
        result.append((target, file_paths))
    return result


# Tcl/Tk paths (Homebrew, Intel Mac)
# Version is discovered dynamically: survives "brew upgrade tcl-tk".
import glob


def _find_tcl_tk():
    """Find tcl/tk dirs in Homebrew Cellar. Returns (tcl_dir, tk_dir)."""
    candidates = sorted(
        glob.glob("/usr/local/Cellar/tcl-tk/*/lib/tcl9.0"),
        reverse=True,
    )
    if not candidates:
        raise RuntimeError(
            "tcl-tk not found in /usr/local/Cellar. "
            "Install it first: brew install tcl-tk"
        )
    tcl_dir = candidates[0]
    tk_dir = tcl_dir.replace("/tcl9.0", "/tk9.0")
    return tcl_dir, tk_dir


TCL_SRC, TK_SRC = _find_tcl_tk()

DATA_FILES = []
DATA_FILES += collect_dir(TCL_SRC, "lib/tcl9.0")
DATA_FILES += collect_dir(TK_SRC, "lib/tk9.0")

OPTIONS = {
    "argv_emulation": False,
    "packages": [
        "app",
        "serial",
        "pyte",
        "usb_plug_notification_darwin",
    ],
    "includes": [
        "tkinter",
        "tkinter.ttk",
        "tkinter.font",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "ctypes",
        "ctypes.util",
        "hashlib",
        "threading",
        "json",
    ],
    "frameworks": [
        "/usr/local/lib/libflashrom.dylib",
    ],
    "plist": {
        "CFBundleName": "SPI and UART Tool",
        "CFBundleDisplayName": "SPI & UART Tool",
        "CFBundleIdentifier": "com.psevdonim-web.spi-uart-tool",
        "CFBundleVersion": "0.3.0",
        "CFBundleShortVersionString": "0.3.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "10.13",
    },
    "iconfile": os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.icns"),
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
