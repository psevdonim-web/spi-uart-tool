"""
Direct access to libflashrom via ctypes.

Uses flashrom_flash_probe_v2 — it returns both flashctx (in our buffer)
and a list of chip names.

libflashrom.dylib search order:
1. Inside .app bundle (Contents/Frameworks/)
2. System paths (/usr/local/lib, /opt/homebrew/lib)
"""

import ctypes
import os
import sys
from ctypes import (
    c_char_p, c_int, c_size_t, c_uint, c_void_p,
    CFUNCTYPE, POINTER,
)


PROGRESS_READ = 0
PROGRESS_WRITE = 1
PROGRESS_ERASE = 2
PROGRESS_VERIFY = 3

FLASHCTX_BUFFER_SIZE = 8192


def _find_libflashrom() -> str:
    """Find libflashrom.dylib: first inside .app, then system paths."""
    candidates = []

    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        frameworks = os.path.abspath(os.path.join(exe_dir, "..", "Frameworks"))
        candidates.append(os.path.join(frameworks, "libflashrom.dylib"))
        candidates.append(os.path.join(frameworks, "libflashrom.1.dylib"))

    candidates.append("/usr/local/lib/libflashrom.dylib")
    candidates.append("/usr/local/lib/libflashrom.1.dylib")
    candidates.append("/opt/homebrew/lib/libflashrom.dylib")
    candidates.append("/opt/homebrew/lib/libflashrom.1.dylib")

    for path in candidates:
        if os.path.isfile(path):
            return path

    return "/usr/local/lib/libflashrom.dylib"


LIB_PATH = _find_libflashrom()


ProgressCallbackV2 = CFUNCTYPE(None, c_int, c_size_t, c_size_t, c_void_p)


class FlashchipInfo(ctypes.Structure):
    """struct flashrom_flashchip_info."""
    _fields_ = [
        ("vendor", c_char_p),
        ("name", c_char_p),
        ("total_size", c_uint),
        ("tested_probe", c_int),
        ("tested_read", c_int),
        ("tested_erase", c_int),
        ("tested_write", c_int),
        ("tested_wp", c_int),
    ]


class LibFlashrom:
    """libflashrom wrapper. One instance per application."""

    def __init__(self):
        self.lib = ctypes.CDLL(LIB_PATH)
        self.flashctx = None
        self.chip_name = None
        self._flashctx_buf = None
        self._cb_ref = None
        self._initialized = False
        self._programmer_ready = False
        self._setup_signatures()

    def _setup_signatures(self):
        lib = self.lib

        lib.flashrom_init.restype = c_int
        lib.flashrom_init.argtypes = [c_int]

        lib.flashrom_programmer_init.restype = c_int
        lib.flashrom_programmer_init.argtypes = [
            POINTER(c_void_p), c_char_p, c_char_p
        ]

        lib.flashrom_flash_probe_v2.restype = c_int
        lib.flashrom_flash_probe_v2.argtypes = [
            c_void_p,
            POINTER(POINTER(c_char_p)),
            c_void_p,
            c_char_p,
        ]

        lib.flashrom_flash_getsize.restype = c_size_t
        lib.flashrom_flash_getsize.argtypes = [c_void_p]

        lib.flashrom_set_progress_callback_v2.restype = None
        lib.flashrom_set_progress_callback_v2.argtypes = [
            c_void_p, ProgressCallbackV2, c_void_p
        ]

        lib.flashrom_image_read.restype = c_int
        lib.flashrom_image_read.argtypes = [c_void_p, c_void_p, c_size_t]

        lib.flashrom_image_write.restype = c_int
        lib.flashrom_image_write.argtypes = [c_void_p, c_void_p, c_size_t]

        lib.flashrom_image_verify.restype = c_int
        lib.flashrom_image_verify.argtypes = [c_void_p, c_void_p, c_size_t]

        lib.flashrom_flash_erase.restype = c_int
        lib.flashrom_flash_erase.argtypes = [c_void_p]

        lib.flashrom_programmer_shutdown.restype = c_int
        lib.flashrom_programmer_shutdown.argtypes = [c_void_p]

        lib.flashrom_shutdown.restype = c_int
        lib.flashrom_shutdown.argtypes = []

        lib.flashrom_supported_flash_chips.restype = c_void_p
        lib.flashrom_supported_flash_chips.argtypes = []

        lib.flashrom_data_free.restype = c_int
        lib.flashrom_data_free.argtypes = [c_void_p]

    def init(self):
        if self._initialized:
            return
        rc = self.lib.flashrom_init(1)
        if rc != 0:
            raise RuntimeError(f"flashrom_init failed: {rc}")
        self._initialized = True

    def _ensure_programmer(self):
        """Call flashrom_programmer_init (required, even though ptr stays None)."""
        if self._programmer_ready:
            return
        ptr = c_void_p()
        rc = self.lib.flashrom_programmer_init(
            ctypes.byref(ptr),
            b"ch341a_spi",
            b"",
        )
        if rc != 0:
            raise RuntimeError(f"programmer_init failed: {rc}")
        self._programmer_ready = True

    def probe_chip(self, chip_name: str = None) -> str:
        """Detect chip. Returns chip name."""
        self._ensure_programmer()

        self.flashctx = None
        self._flashctx_buf = None

        self._flashctx_buf = ctypes.create_string_buffer(FLASHCTX_BUFFER_SIZE)

        names_var = POINTER(c_char_p)()
        names_ptr = ctypes.pointer(names_var)

        rc = self.lib.flashrom_flash_probe_v2(
            self._flashctx_buf,
            names_ptr,
            None,
            chip_name.encode() if chip_name else None,
        )

        if rc < 0:
            raise RuntimeError(f"flash_probe_v2 error: rc={rc}")
        if rc == 0:
            raise RuntimeError("Chip not found (0 matches)")

        matched = []
        if names_var:
            i = 0
            while i < 20:
                name = names_var[i]
                if name is None:
                    break
                matched.append(name.decode())
                i += 1

        if chip_name:
            self.chip_name = chip_name
        elif matched:
            self.chip_name = matched[0]
        else:
            self.chip_name = None

        self.flashctx = ctypes.cast(self._flashctx_buf, c_void_p)
        return self.chip_name

    def has_chip(self) -> bool:
        return self.flashctx is not None

    def get_size(self) -> int:
        if not self.flashctx:
            raise RuntimeError("Chip not detected")
        return self.lib.flashrom_flash_getsize(self.flashctx)

    def get_name(self) -> str:
        return self.chip_name or "auto"

    def supported_flash_chips(self):
        """Return list of supported chip names."""
        try:
            ptr = self.lib.flashrom_supported_flash_chips()
            if not ptr:
                return []

            chips = []
            info_array = ctypes.cast(ptr, POINTER(FlashchipInfo))
            i = 0
            while True:
                item = info_array[i]
                if not item.name:
                    break
                chips.append(item.name.decode("utf-8", errors="replace"))
                i += 1
                if i > 10000:
                    break

            try:
                self.lib.flashrom_data_free(ptr)
            except Exception:
                pass

            return sorted(set(chips))
        except Exception as e:
            print(f"[libflashrom] supported_flash_chips error: {e}", flush=True)
            return []

    def set_progress_callback(self, py_callback):
        """Set progress callback. py_callback(stage, current, total, user_data)."""
        if not self.flashctx:
            raise RuntimeError("Chip not detected")

        def c_callback(stage, current, total, user_data):
            try:
                py_callback(stage, current, total, user_data)
            except Exception as e:
                print(f"[callback error] {e}", flush=True)

        self._cb_ref = ProgressCallbackV2(c_callback)
        self.lib.flashrom_set_progress_callback_v2(
            self.flashctx, self._cb_ref, None
        )

    def read(self, buffer):
        return self.lib.flashrom_image_read(
            self.flashctx, buffer, c_size_t(len(buffer))
        )

    def write(self, buffer):
        return self.lib.flashrom_image_write(
            self.flashctx, buffer, c_size_t(len(buffer))
        )

    def verify(self, buffer):
        return self.lib.flashrom_image_verify(
            self.flashctx, buffer, c_size_t(len(buffer))
        )

    def erase(self):
        return self.lib.flashrom_flash_erase(self.flashctx)

    def close(self):
        """Release USB device."""
        try:
            self.lib.flashrom_programmer_shutdown(None)
        except Exception:
            pass
        try:
            if self._initialized:
                self.lib.flashrom_shutdown()
        except Exception:
            pass
        self.flashctx = None
        self._flashctx_buf = None
        self._programmer_ready = False
        self._initialized = False
