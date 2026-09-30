"""
USB hotplug monitor for CH341A via usb-plug-notification-darwin.

Logic:
- plug from 0x5512  -> mode = "SPI"
- plug from 0x5523  -> mode = "UART"
- unplug from X     -> if current mode was X -> mode = None
- on startup — one-time check via system_profiler
"""

import threading
import time
from typing import Callable, Optional


PID_SPI = 0x5512
PID_UART = 0x5523
VID_CH341A = 0x1A86


class UsbMonitor:
    """Background USB event monitor for CH341A."""

    def __init__(self):
        self._spi_present = False
        self._uart_present = False
        self.current_mode: Optional[str] = None
        self._on_change: Optional[Callable[[Optional[str]], None]] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def set_on_change(self, callback):
        self._on_change = callback

    def get_mode(self) -> Optional[str]:
        with self._lock:
            return self._compute_mode()

    def _compute_mode(self) -> Optional[str]:
        if self._spi_present:
            return "SPI"
        if self._uart_present:
            return "UART"
        return None

    def _update(self):
        """Recompute mode and fire callback on change."""
        with self._lock:
            new_mode = self._compute_mode()
            if new_mode == self.current_mode:
                return
            self.current_mode = new_mode

        if self._on_change:
            try:
                self._on_change(new_mode)
            except Exception as e:
                print(f"[usb_monitor] on_change error: {e}", flush=True)

    def _on_spi_event(self, action):
        with self._lock:
            if action == "plug":
                self._spi_present = True
                self._uart_present = False
            elif action == "unplug":
                self._spi_present = False
        self._update()

    def _on_uart_event(self, action):
        with self._lock:
            if action == "plug":
                self._uart_present = True
                self._spi_present = False
            elif action == "unplug":
                self._uart_present = False
        self._update()

    def start(self):
        self._stop.clear()
        self._detect_initial()

        t_spi = threading.Thread(target=self._listen_spi, daemon=True)
        t_spi.start()

        t_uart = threading.Thread(target=self._listen_uart, daemon=True)
        t_uart.start()

    def stop(self):
        self._stop.set()

    def _listen_spi(self):
        try:
            from usb_plug_notification_darwin.main import _main
        except ImportError as e:
            print(f"[usb_monitor] Package not found: {e}", flush=True)
            return
        _main(VID_CH341A, PID_SPI, self._on_spi_event)

    def _listen_uart(self):
        try:
            from usb_plug_notification_darwin.main import _main
        except ImportError as e:
            print(f"[usb_monitor] Package not found: {e}", flush=True)
            return
        _main(VID_CH341A, PID_UART, self._on_uart_event)

    def _detect_initial(self):
        """One-time check on startup: what is already connected."""
        import subprocess
        try:
            out = subprocess.run(
                ["system_profiler", "SPUSBDataType"],
                capture_output=True, text=True, timeout=10
            )
            text = out.stdout
        except Exception:
            return

        with self._lock:
            if "0x5512" in text and "0x1a86" in text:
                self._spi_present = True
                self._uart_present = False
            elif "0x5523" in text and "0x1a86" in text:
                self._uart_present = True
                self._spi_present = False
            else:
                self._spi_present = False
                self._uart_present = False
            self.current_mode = self._compute_mode()
