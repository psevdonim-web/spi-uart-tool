"""
Main application window.

Sections: SPI, UART, Settings.
System log is written to ~/Library/Logs/SPI-UART-Tool/app.log
"""

import os
import signal
import tkinter as tk
from tkinter import ttk

from .spi_tab import SpiTab
from .uart_tab import UartTab
from .settings_tab import SettingsTab
from ..core.libflashrom import LibFlashrom
from ..core.usb_monitor import UsbMonitor
from ..core.usb_devices import scan_wch_devices, find_programmer
from ..core.logger import Logger
from ..core.config import Config
from ..version import APP_NAME, APP_VERSION


class MainWindow:
    """Main window."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        self.root.resizable(True, True)

        # ---- Logger ----
        self.logger = Logger()

        # ---- Config ----
        self.config = Config()

        # ---- LibFlashrom ----
        self.lib = None
        self.lib_ready = False
        self.lib_error = None

        # ---- USB monitor ----
        self.monitor = UsbMonitor()
        self.monitor.set_on_change(self._on_mode_change_thread)
        self.monitor.start()

        # ---- Busy flag ----
        self.busy = False

        # ---- Initial section flag ----
        self._initial_section_done = False

        # ---- Current section ----
        self.current_section = None

        # ---- Closing flag ----
        self._closing = False

        # ---- Build UI ----
        self._build_topbar()

        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(side="top", fill="both", expand=True,
                             pady=(0, 50))

        self._build_content()

        # ---- Delayed initial section ----
        self.root.after(800, self._initial_section)

        # ---- Periodic mode check ----
        self.root.after(500, self._poll_mode)

        # ---- Close handlers ----
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        try:
            self.root.createcommand("::tk::mac::Quit", self._on_close)
        except Exception:
            pass

        try:
            signal.signal(signal.SIGTERM, self._on_sigterm)
        except Exception:
            pass

    # =========================================================
    # LOGGING
    # =========================================================
    def log(self, msg: str):
        self.logger.log(msg)

    # =========================================================
    # USB SCAN (startup)
    # =========================================================
    def _log_usb_devices(self):
        """Scan USB at startup and log all WCH devices found."""
        try:
            devices = scan_wch_devices()
            if not devices:
                self.log("[sys] USB scan: no WCH devices found")
                return
            for d in devices:
                mark = "OK" if d.known else "UNKNOWN"
                self.log(f"[sys] USB scan: 0x{d.vid:04x}:0x{d.pid:04x} - "
                         f"{d.name} [{mark}]")
                if not d.known:
                    self.log(f"[warn] Unknown WCH device (0x{d.pid:04x}). "
                             f"Programmer may not work.")
                    self.log("[warn] Go to Settings and enter PID manually "
                             "if you know it.")
        except Exception as e:
            self.log(f"[err] USB scan failed: {e}")

    # =========================================================
    # INITIAL SECTION
    # =========================================================
    def _initial_section(self):
        if self._initial_section_done:
            return
        self._initial_section_done = True

        self._log_usb_devices()

        mode = self.monitor.get_mode()
        if mode == "UART":
            self.show_section("UART")
        else:
            self.show_section("SPI")

    # =========================================================
    # PROGRAMMER MODE
    # =========================================================
    def _on_mode_change_thread(self, mode):
        pass

    def _poll_mode(self):
        if self._closing:
            return
        mode = self.monitor.get_mode()
        self._apply_mode(mode)
        self.root.after(500, self._poll_mode)

    def _apply_mode(self, mode):
        if mode == "SPI":
            self.lbl_prog_mode.configure(text="SPI", foreground="#4ec9b0")
        elif mode == "UART":
            self.lbl_prog_mode.configure(text="UART", foreground="#dcdcaa")
        else:
            self.lbl_prog_mode.configure(text="none", foreground="#f44747")

        if mode == "SPI":
            if not self.lib_ready and not self.busy:
                self._open_lib()
        else:
            if self.lib_ready and not self.busy:
                self._close_lib()

    def _open_lib(self):
        try:
            self.lib = LibFlashrom()
            self.lib.init()
            self.lib_ready = True
            self.lib_error = None
            self.log("[sys] SPI programmer opened")
            self._propagate_lib_to_spi()
        except Exception as e:
            self.lib = None
            self.lib_ready = False
            self.lib_error = str(e)
            self.log(f"[err] Could not open programmer: {e}")

    def _close_lib(self):
        if self.lib:
            try:
                self.lib.close()
            except Exception:
                pass
        self.lib = None
        self.lib_ready = False
        self.log("[sys] Programmer closed")
        self._propagate_lib_to_spi()

    def _propagate_lib_to_spi(self):
        try:
            self.spi_tab.update_lib(self.lib, self.lib_ready)
        except Exception:
            pass

    # =========================================================
    # FONT SIZE
    # =========================================================
    def _apply_font_size(self, size: int):
        try:
            self.spi_tab.set_font_size(size)
        except Exception:
            pass
        try:
            self.uart_tab.set_font_size(size)
        except Exception:
            pass
        self.log(f"[sys] Font size: {size}")

    # =========================================================
    # TOPBAR
    # =========================================================
    def _build_topbar(self):
        topbar = ttk.Frame(self.root)
        topbar.pack(side="top", fill="x")

        ttk.Label(topbar, text=APP_NAME,
                  font=("Helvetica", 13, "bold")).pack(side="left", padx=(12, 20))

        self.section_labels = {}
        for name in ["SPI", "UART", "Settings"]:
            lbl = tk.Label(topbar, text=name,
                           font=("Helvetica", 10),
                           fg="#c0c0c0",
                           cursor="pointinghand")
            lbl.pack(side="left", padx=7, pady=4)
            lbl.bind("<Button-1>", lambda e, n=name: self.show_section(n))
            self.section_labels[name] = lbl

        self.lbl_prog_mode = ttk.Label(topbar, text="—", foreground="#808080")
        self.lbl_prog_mode.pack(side="right", padx=(0, 12))

        ttk.Label(topbar, text="Programmer:").pack(side="right", padx=(0, 6))

    # =========================================================
    # CONTENT
    # =========================================================
    def _build_content(self):
        self.content_area = ttk.Frame(self.main_frame)
        self.content_area.pack(side="left", fill="both", expand=True)

        self.spi_tab = SpiTab(self.content_area,
                              root=self.root,
                              lib=self.lib,
                              lib_ready=self.lib_ready,
                              logger=self.logger,
                              config=self.config)
        self.uart_tab = UartTab(self.content_area,
                                root=self.root,
                                logger=self.logger,
                                config=self.config)
        self.settings_tab = SettingsTab(self.content_area,
                                        root=self.root,
                                        logger=self.logger,
                                        config=self.config,
                                        on_apply_font=self._apply_font_size)

        self.section_frames = {
            "SPI": self.spi_tab,
            "UART": self.uart_tab,
            "Settings": self.settings_tab,
        }

    def show_section(self, name: str):
        if self.current_section == "Settings" and name != "Settings":
            try:
                self.settings_tab.on_hide()
            except Exception:
                pass

        for f in self.section_frames.values():
            f.pack_forget()
        self.section_frames[name].pack(fill="both", expand=True)

        for lbl_name, lbl in self.section_labels.items():
            if lbl_name == name:
                lbl.configure(fg="#007aff")
            else:
                lbl.configure(fg="#c0c0c0")

        if name == "Settings":
            try:
                self.settings_tab.on_show()
            except Exception:
                pass

        self.current_section = name

    # =========================================================
    # CLOSING
    # =========================================================
    def _on_sigterm(self, signum, frame):
        try:
            self.root.after(0, self._on_close)
        except Exception:
            pass

    def _on_close(self, *args, **kwargs):
        if self._closing:
            return
        self._closing = True

        self.log("[sys] Closing application...")

        try:
            self.monitor.stop()
        except Exception:
            pass

        try:
            self.uart_tab.terminal.close()
        except Exception:
            pass

        try:
            self.settings_tab.on_hide()
        except Exception:
            pass

        if self.lib:
            try:
                self.lib.close()
            except Exception:
                pass

        try:
            self.root.destroy()
        except Exception:
            pass

        self.log("[sys] Application closed")
        os._exit(0)

    # =========================================================
    # RUN
    # =========================================================
    def run(self):
        self.log(f"[sys] {APP_NAME} v{APP_VERSION} started")
        self.root.mainloop()
