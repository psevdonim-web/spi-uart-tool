"""
SPI tab: read, save, write, verify, erase via libflashrom.
"""

import os
import time
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .common import (
    LOG_BG, LOG_FG, LOG_SEL_BG,
    SPI_LABEL_WIDTH, BTN_WIDTH,
    attach_text_context_menu, draw_progress,
    PROG_READ, PROG_VERIFY, PROG_WRITE, PROG_ERASE, PROG_DEFAULT,
)
from ..core.chip_detector import detect_chip
from ..core.chip_lister import list_chips
from ..core.spi_reader import read_chip
from ..core.spi_verifier import verify_chip
from ..core.spi_writer import write_chip
from ..core.spi_eraser import erase_chip
from ..utils.background import run_in_background


CACHE_DIR = os.path.expanduser("~/Library/Caches/SPI-UART-Tool")


class SpiTab(ttk.Frame):
    """SPI tab."""

    def __init__(self, parent, root, lib, lib_ready, logger, config):
        super().__init__(parent)
        self.root = root
        self.lib = lib
        self.lib_ready = lib_ready
        self.logger = logger
        self.config = config
        self._busy = False

        self.last_dump_path = None
        self.last_dump_sha = None
        self.last_dump_size = None

        # ---------- Top: operation buttons ----------
        top = ttk.Frame(self)
        top.pack(side="top", fill="x")

        op_row = ttk.Frame(top)
        op_row.pack(anchor="center", pady=(12, 4))

        self.btn_read = ttk.Button(op_row, text="Read", width=BTN_WIDTH,
                                   command=self._on_read_click)
        self.btn_read.pack(side="left", padx=4)

        self.btn_save = ttk.Button(op_row, text="Save", width=BTN_WIDTH,
                                   command=self._on_save_click)
        self.btn_save.pack(side="left", padx=4)

        self.btn_write = ttk.Button(op_row, text="Write", width=BTN_WIDTH,
                                    command=self._on_write_click)
        self.btn_write.pack(side="left", padx=4)

        self.btn_verify = ttk.Button(op_row, text="Verify", width=BTN_WIDTH,
                                     command=self._on_verify_click)
        self.btn_verify.pack(side="left", padx=4)

        self.btn_erase = ttk.Button(op_row, text="Erase", width=BTN_WIDTH,
                                    command=self._on_erase_click)
        self.btn_erase.pack(side="left", padx=4)

        self._op_buttons = [
            self.btn_read, self.btn_save, self.btn_write,
            self.btn_verify, self.btn_erase,
        ]

        # ---------- Auto-verify checkboxes ----------
        self.auto_verify_after_read = tk.BooleanVar(value=False)
        self.auto_verify_after_write = tk.BooleanVar(value=True)

        checks_row = ttk.Frame(top)
        checks_row.pack(anchor="center", pady=(0, 6))

        ttk.Checkbutton(checks_row, text="Verify after read",
                        variable=self.auto_verify_after_read).pack(side="left", padx=8)
        ttk.Checkbutton(checks_row, text="Verify after write",
                        variable=self.auto_verify_after_write).pack(side="left", padx=8)

        # ---------- Bottom: chip, file, progress ----------
        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x")
        bottom.columnconfigure(1, weight=1)

        ttk.Label(bottom, text="Chip:", width=SPI_LABEL_WIDTH, anchor="e").grid(
            row=0, column=0, sticky="e", padx=(12, 6), pady=6)

        self.chip_var = tk.StringVar(value="")
        self.chip_combo = ttk.Combobox(
            bottom, textvariable=self.chip_var,
            values=["", "GD25B128B/GD25Q128B", "GD25Q512", "W25Q128", "MX25L128"],
            width=25)
        self.chip_combo.grid(row=0, column=1, sticky="ew", pady=6)

        chip_btns = ttk.Frame(bottom)
        chip_btns.grid(row=0, column=2, sticky="w", padx=(6, 12), pady=6)

        self.btn_detect = ttk.Button(chip_btns, text="Detect",
                                     command=self._on_detect_click)
        self.btn_detect.pack(side="left", padx=2)

        self.btn_refresh_chips = ttk.Button(chip_btns, text="Refresh list",
                                            command=self._on_refresh_chips_click)
        self.btn_refresh_chips.pack(side="left", padx=2)

        ttk.Label(bottom, text="File:", width=SPI_LABEL_WIDTH, anchor="e").grid(
            row=1, column=0, sticky="e", padx=(12, 6), pady=6)

        self.file_var = tk.StringVar(value="")
        self.file_entry = ttk.Entry(bottom, textvariable=self.file_var)
        self.file_entry.grid(row=1, column=1, sticky="ew", pady=6)

        file_btns = ttk.Frame(bottom)
        file_btns.grid(row=1, column=2, sticky="w", padx=(6, 12), pady=6)

        self.btn_browse = ttk.Button(file_btns, text="Browse...",
                                     command=self._on_browse_click)
        self.btn_browse.pack(side="left", padx=2)

        ttk.Label(bottom, text="Progress:", width=SPI_LABEL_WIDTH, anchor="e").grid(
            row=2, column=0, sticky="e", padx=(12, 6), pady=(6, 12))

        self.prog_canvas = tk.Canvas(bottom, height=20, bg=LOG_BG,
                                     highlightthickness=0, bd=0)
        self.prog_canvas.grid(row=2, column=1, sticky="ew",
                              padx=(3, 2), pady=(6, 12))
        self._last_progress = 0
        self._last_progress_color = None
        self.prog_canvas.bind("<Configure>", self._redraw_progress)

        self.prog_label_var = tk.StringVar(value="")
        self.prog_label = tk.Label(bottom, textvariable=self.prog_label_var,
                                   font=("Menlo", 10), anchor="w")
        self.prog_label.grid(row=2, column=2, sticky="w",
                             padx=(6, 12), pady=(6, 12))


        # ---------- Middle: log ----------
        log_frame = ttk.LabelFrame(self, text="SPI log")
        log_frame.pack(side="top", fill="both", expand=True, padx=12, pady=6)

        try:
            _font_size = int(self.config.get("font_size") or 11)
        except (ValueError, TypeError):
            _font_size = 11

        self.log = tk.Text(log_frame, wrap="word", font=("Menlo", _font_size),
                           bg=LOG_BG, fg=LOG_FG, insertbackground=LOG_FG,
                           selectbackground=LOG_SEL_BG,
                           relief="solid", borderwidth=1)
        self.log.pack(fill="both", expand=True, padx=4, pady=4)

        attach_text_context_menu(self.log)

        self._other_buttons = [
            self.btn_detect, self.btn_refresh_chips,
            self.btn_browse,
        ]

        if self.lib_ready:
            self.log_write("[sys] SPI log ready. Programmer is open.")
        else:
            self.log_write("[sys] SPI log ready. Waiting for programmer.")

    # ---------- Public methods ----------
    def log_write(self, msg: str):
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        try:
            self.logger.log(msg)
        except Exception:
            pass

    def set_progress(self, value: int, max_value: int = 100, color=None):
        self._last_progress = value
        self._last_progress_color = color
        draw_progress(self.prog_canvas, value, max_value, color=color)
        _LABELS = {
            PROG_READ: "Read",
            PROG_VERIFY: "Verify",
            PROG_WRITE: "Write",
            PROG_ERASE: "Erase",
        }
        text = _LABELS.get(color, "")
        self.prog_label_var.set(text)
        self.prog_label.config(fg=color or PROG_DEFAULT)

    def set_result(self, ok: bool):
        if ok:
            self.prog_label_var.set("OK")
            self.prog_label.config(fg=PROG_READ)
        else:
            self.prog_label_var.set("Failed")
            self.prog_label.config(fg=PROG_WRITE)

    def _redraw_progress(self, event=None):
        draw_progress(self.prog_canvas, self._last_progress,
                      color=self._last_progress_color)

    def update_lib(self, lib, lib_ready: bool):
        self.lib = lib
        self.lib_ready = lib_ready
        if lib_ready:
            self.log_write("[sys] SPI programmer available")
        else:
            self.log_write("[sys] SPI programmer unavailable")

    def set_font_size(self, size: int):
        try:
            size = int(size)
        except (ValueError, TypeError):
            return
        if size < 6 or size > 40:
            return
        try:
            self.log.config(font=("Menlo", size))
        except Exception:
            pass

    # ---------- Helpers ----------
    def _get_dumps_dir(self) -> str:
        path = self.config.get("dumps_dir") or "~/Documents/SPI_UART_Tool/dumps"
        return os.path.expanduser(path)

    def _block_buttons(self, blocked: bool, active_btn=None):
        self._busy = blocked
        for btn in self._op_buttons:
            if blocked and btn is active_btn:
                btn.config(state="disabled")
            else:
                btn.config(state="normal")
        for btn in self._other_buttons:
            btn.config(state="disabled" if blocked else "normal")

    def _ensure_cache_dir(self):
        os.makedirs(CACHE_DIR, exist_ok=True)

    def _get_chip(self) -> str:
        chip = self.chip_var.get().strip()
        if chip in ("", "auto"):
            return ""
        return chip

    def _progress_via_after(self, p, color=None):
        self.root.after(0, lambda: self.set_progress(p, color=color))

    def _make_progress_cb(self, color):
        def cb(p):
            self._progress_via_after(p, color=color)
        return cb

    def _log_via_after(self, msg):
        self.root.after(0, lambda: self.log_write(msg))

    # ---------- Handlers ----------
    def _on_detect_click(self):
        if not self.lib_ready:
            self.log_write("[err] Programmer is not open.")
            return

        chip = self._get_chip()
        chip_for_detect = chip if chip else None

        if chip_for_detect:
            self.log_write(f"[sys] Detecting chip (with name: {chip_for_detect})...")
        else:
            self.log_write("[sys] Auto-detecting chip...")

        self.btn_detect.config(state="disabled")

        def work():
            return detect_chip(self.lib, chip_for_detect)

        def done(result, error):
            self.btn_detect.config(state="normal")
            if error:
                self.log_write(f"[err] Error: {error}")
                return
            if result.ok:
                self.log_write(f"[ok] Found chip: {result.chip} "
                               f"({result.size_kb} KB)")
                self.chip_var.set(result.chip)
            else:
                self.log_write(f"[err] {result.error}")

        run_in_background(self.root, work, done)

    def _on_browse_click(self):
        initial_dir = None
        current = self.file_var.get().strip()
        if current:
            initial_dir = os.path.dirname(os.path.expanduser(current))
        else:
            initial_dir = self._get_dumps_dir()

        path = filedialog.askopenfilename(
            title="Select file",
            initialdir=initial_dir,
            filetypes=[("Binary files", "*.bin"), ("All files", "*.*")],
        )
        if path:
            self.file_var.set(path)
            self.log_write(f"[sys] File selected: {path}")

    def _on_refresh_chips_click(self):
        if not self.lib_ready:
            self.log_write("[err] Programmer is not open.")
            return

        self.btn_refresh_chips.config(state="disabled")
        self.log_write("[sys] Loading supported chip list...")

        def work():
            return list_chips(self.lib)

        def done(chips, error):
            self.btn_refresh_chips.config(state="normal")
            if error:
                self.log_write(f"[err] Error: {error}")
                return
            if not chips:
                self.log_write("[err] Could not get chip list.")
                return
            self.log_write(f"[ok] Loaded chips: {len(chips)}")
            values = [""] + chips
            self.chip_combo.config(values=values)

        run_in_background(self.root, work, done)

    # ---------- READ ----------
    def _on_read_click(self):
        if self._busy:
            return
        if not self.lib_ready:
            self.log_write("[err] Programmer is not open.")
            return

        if not self.lib.has_chip():
            self.log_write("[sys] Chip not detected. Press 'Detect'.")
            return

        chip = self._get_chip() or self.lib.get_name() or "auto"

        self._ensure_cache_dir()
        safe_chip = chip.replace("/", "_")
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(CACHE_DIR, f"dump_{safe_chip}_{ts}.bin")

        self._block_buttons(True, self.btn_read)
        self.set_progress(0, color=PROG_READ)
        self.log_write(f"[sys] Reading chip ({chip})...")
        self.log_write(f"[sys] Temp file: {out_path}")

        t_start = time.time()

        def on_done_bg(ok, msg, sha):
            self.root.after(0, lambda: finish(ok, msg, sha))

        def work():
            read_chip(
                lib=self.lib,
                chip=chip,
                out_path=out_path,
                on_progress=self._make_progress_cb(PROG_READ),
                on_log=self._log_via_after,
                on_done=on_done_bg,
            )
            return None

        def finish(ok, msg, sha):
            elapsed = round(time.time() - t_start, 1)
            self._block_buttons(False)
            if ok:
                self.set_progress(100, color=PROG_READ)
                self.set_result(True)
                self.last_dump_path = out_path
                self.last_dump_sha = sha
                self.last_dump_size = (os.path.getsize(out_path)
                                       if os.path.isfile(out_path) else None)
                self.log_write(f"[ok] {msg}")
                self.log_write(f"[ok] Time: {elapsed} s")
                if sha:
                    self.log_write(f"[ok] SHA256: {sha}")
                self.log_write("[sys] Dump in memory. Press 'Save'.")

                if self.auto_verify_after_read.get():
                    self.log_write("[sys] Auto-verify after read...")
                    self._run_verify(out_path)
            else:
                self.log_write(f"[err] {msg}")
                self.set_progress(0)
                self.set_result(False)

        run_in_background(self.root, work, lambda r, e: None)

    # ---------- SAVE ----------
    def _on_save_click(self):
        if not self.last_dump_path or not os.path.isfile(self.last_dump_path):
            self.log_write("[err] No dump in memory. Read chip first.")
            return

        chip_field = self._get_chip() or self.lib.get_name() or "auto"
        chip = chip_field.replace("/", "_")
        ts = time.strftime("%Y%m%d_%H%M")
        default_name = f"dump_{chip}_{ts}.bin"

        initial_dir = self._get_dumps_dir()
        if not os.path.isdir(initial_dir):
            initial_dir = os.path.expanduser("~")

        out_path = filedialog.asksaveasfilename(
            title="Save dump",
            initialdir=initial_dir,
            initialfile=default_name,
            defaultextension=".bin",
            filetypes=[("Binary files", "*.bin"), ("All files", "*.*")],
        )
        if not out_path:
            self.log_write("[sys] Save cancelled.")
            return

        try:
            shutil.copy2(self.last_dump_path, out_path)
            self.log_write(f"[ok] Saved: {out_path}")
        except Exception as e:
            self.log_write(f"[err] Could not save: {e}")

    # ---------- WRITE ----------
    def _on_write_click(self):
        if self._busy:
            return
        if not self.lib_ready:
            self.log_write("[err] Programmer is not open.")
            return

        if not self.lib.has_chip():
            self.log_write("[sys] Chip not detected. Press 'Detect'.")
            return

        chip = self._get_chip() or self.lib.get_name() or "auto"

        file_path = self.file_var.get().strip()
        if not file_path:
            self.log_write("[err] No file selected for writing.")
            return
        file_path = os.path.expanduser(file_path)
        if not os.path.isfile(file_path):
            self.log_write(f"[err] File not found: {file_path}")
            return

        ok = messagebox.askyesno(
            "Confirm write",
            f"Write file:\n{file_path}\n\n"
            f"to chip: {chip}\n\n"
            f"Chip contents will be ERASED and OVERWRITTEN.\n\n"
            f"Continue?",
            icon="warning",
        )
        if not ok:
            self.log_write("[sys] Write cancelled.")
            return

        self._block_buttons(True, self.btn_write)
        self.set_progress(0, color=PROG_WRITE)
        self.log_write(f"[sys] Writing to chip ({chip})...")
        self.log_write(f"[sys] File: {file_path}")

        t_start = time.time()

        def on_done_bg(ok, msg):
            self.root.after(0, lambda: finish(ok, msg))

        def work():
            write_chip(
                lib=self.lib,
                chip=chip,
                file_path=file_path,
                on_progress=self._make_progress_cb(PROG_WRITE),
                on_log=self._log_via_after,
                on_done=on_done_bg,
            )
            return None

        def finish(ok, msg):
            elapsed = round(time.time() - t_start, 1)
            self._block_buttons(False)
            if ok:
                self.set_progress(100, color=PROG_WRITE)
                self.set_result(True)
                self.log_write(f"[ok] {msg}")
                self.log_write(f"[ok] Time: {elapsed} s")

                if self.auto_verify_after_write.get():
                    self.log_write("[sys] Auto-verify after write...")
                    self._run_verify(file_path)
            else:
                self.log_write(f"[err] {msg}")
                self.set_progress(0)
                self.set_result(False)

        run_in_background(self.root, work, lambda r, e: None)

    # ---------- VERIFY ----------
    def _on_verify_click(self):
        if self._busy:
            return
        if not self.lib_ready:
            self.log_write("[err] Programmer is not open.")
            return

        if not self.lib.has_chip():
            self.log_write("[sys] Chip not detected. Press 'Detect'.")
            return

        file_path = self.file_var.get().strip()
        if not file_path:
            self.log_write("[err] No file selected for verification.")
            return
        file_path = os.path.expanduser(file_path)
        if not os.path.isfile(file_path):
            self.log_write(f"[err] File not found: {file_path}")
            return

        self._run_verify(file_path)

    def _run_verify(self, file_path: str):
        chip = self._get_chip() or self.lib.get_name() or "auto"

        self._block_buttons(True, self.btn_verify)
        self.set_progress(0, color=PROG_VERIFY)
        self.log_write(f"[sys] Verifying chip ({chip}) against file:")
        self.log_write(f"[sys] {file_path}")

        t_start = time.time()

        def on_done_bg(ok, msg):
            self.root.after(0, lambda: finish(ok, msg))

        def work():
            verify_chip(
                lib=self.lib,
                chip=chip,
                file_path=file_path,
                on_progress=self._make_progress_cb(PROG_VERIFY),
                on_log=self._log_via_after,
                on_done=on_done_bg,
            )
            return None

        def finish(ok, msg):
            elapsed = round(time.time() - t_start, 1)
            self._block_buttons(False)
            if ok:
                self.set_progress(100, color=PROG_VERIFY)
                self.set_result(True)
                self.log_write(f"[ok] {msg}")
                self.log_write(f"[ok] Time: {elapsed} s")
            else:
                self.log_write(f"[err] {msg}")
                self.log_write(f"[err] Time: {elapsed} s")
                self.set_result(False)

        run_in_background(self.root, work, lambda r, e: None)

    # ---------- ERASE ----------
    def _on_erase_click(self):
        if self._busy:
            return
        if not self.lib_ready:
            self.log_write("[err] Programmer is not open.")
            return

        if not self.lib.has_chip():
            self.log_write("[sys] Chip not detected. Press 'Detect'.")
            return

        chip = self._get_chip() or self.lib.get_name() or "auto"

        ok = messagebox.askyesno(
            "Confirm erase",
            f"Erase chip: {chip}\n\n"
            f"All chip contents will be DELETED.\n\n"
            f"Continue?",
            icon="warning",
        )
        if not ok:
            self.log_write("[sys] Erase cancelled.")
            return

        self._block_buttons(True, self.btn_erase)
        self.set_progress(0, color=PROG_ERASE)
        self.log_write(f"[sys] Erasing chip ({chip})...")

        t_start = time.time()

        def on_done_bg(ok, msg):
            self.root.after(0, lambda: finish(ok, msg))

        def work():
            erase_chip(
                lib=self.lib,
                chip=chip,
                on_progress=self._make_progress_cb(PROG_ERASE),
                on_log=self._log_via_after,
                on_done=on_done_bg,
            )
            return None

        def finish(ok, msg):
            elapsed = round(time.time() - t_start, 1)
            self._block_buttons(False)
            if ok:
                self.set_progress(100, color=PROG_ERASE)
                self.set_result(True)
                self.log_write(f"[ok] {msg}")
                self.log_write(f"[ok] Time: {elapsed} s")
            else:
                self.log_write(f"[err] {msg}")
                self.set_progress(0)
                self.set_result(False)

        run_in_background(self.root, work, lambda r, e: None)
