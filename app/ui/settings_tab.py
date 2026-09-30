"""
Settings tab: paths, folders, ports, log theme, font size, logs.
"""

import os
from tkinter import ttk, messagebox


class SettingsTab(ttk.Frame):
    """Settings tab."""

    def __init__(self, parent, root, logger, config,
                 on_apply_font=None):
        super().__init__(parent)
        self.root = root
        self.logger = logger
        self.config = config
        self.on_apply_font = on_apply_font
        self._auto_refresh_id = None

        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="Settings",
                  font=("Helvetica", 12, "bold")).grid(
            row=0, column=0, columnspan=2,
            sticky="w", padx=12, pady=(12, 6))

        # 1. Dumps folder
        self.dumps_var = ttk.Combobox(
            self,
            values=["~/Documents/SPI_UART_Tool/dumps",
                    "~/Desktop",
                    "~/Downloads"],
            state="normal")
        self._add_row(1, "Dumps folder:", self.dumps_var)

        # 2. Last UART port
        self.lastport_var = ttk.Combobox(
            self,
            values=["/dev/cu.wchusbserial1420",
                    "/dev/cu.wchusbserial1410",
                    "/dev/cu.usbserial-0001"],
            state="normal")
        self._add_row(2, "Last UART port:", self.lastport_var)

        # 3. Default UART baud rate
        self.baud_var = ttk.Combobox(
            self,
            values=["9600", "19200", "38400", "57600", "115200",
                    "230400", "460800", "921600"])
        self._add_row(3, "Default UART baud rate:", self.baud_var)

        # 4. Font size
        self.font_var = ttk.Combobox(
            self,
            values=["8", "9", "10", "11", "12", "13", "14", "16", "18", "20"],
            state="normal",
            width=8)
        self._add_row(4, "Log font size:", self.font_var)

        # 5. Log theme
        self.theme_var = ttk.Combobox(
            self,
            values=["system", "light", "dark"])
        self._add_row(5, "Log theme:", self.theme_var)

        # ---------- Separator ----------
        ttk.Separator(self, orient="horizontal").grid(
            row=6, column=0, columnspan=2, sticky="ew", padx=12, pady=(16, 8))

        # ---------- System log section ----------
        ttk.Label(self, text="System log",
                  font=("Helvetica", 11, "bold")).grid(
            row=7, column=0, columnspan=2,
            sticky="w", padx=12, pady=(4, 6))

        self.log_path_var = ttk.Entry(self)
        display_path = self.logger.path
        home = os.path.expanduser("~")
        if display_path.startswith(home):
            display_path = "~" + display_path[len(home):]
        self.log_path_var.insert(0, display_path)
        self.log_path_var.config(state="readonly")
        self._add_row(8, "Log path:", self.log_path_var)

        self.log_size_var = ttk.Entry(self)
        self.log_size_var.insert(0, self.logger.get_size_human())
        self.log_size_var.config(state="readonly")
        self._add_row(9, "Log size:", self.log_size_var)

        log_btns = ttk.Frame(self)
        log_btns.grid(row=10, column=0, columnspan=2,
                      sticky="w", padx=12, pady=(6, 6))

        ttk.Button(log_btns, text="Open log",
                   command=self._on_open_log).pack(side="left", padx=(0, 6))

        ttk.Button(log_btns, text="Clear log",
                   command=self._on_clear_log).pack(side="left", padx=6)

        # ---------- Separator ----------
        ttk.Separator(self, orient="horizontal").grid(
            row=11, column=0, columnspan=2, sticky="ew", padx=12, pady=(16, 8))

        self.btn_save = ttk.Button(self, text="Save settings",
                                   command=self._on_save_settings)
        self.btn_save.grid(row=12, column=0, sticky="w", padx=12, pady=(0, 12))

        self._load_from_config()

    # ---------- Public methods ----------
    def on_show(self):
        self._refresh_size()
        self._schedule_auto_refresh()

    def on_hide(self):
        if self._auto_refresh_id is not None:
            try:
                self.root.after_cancel(self._auto_refresh_id)
            except Exception:
                pass
            self._auto_refresh_id = None

    # ---------- Load / save ----------
    def _load_from_config(self):
        def _set(widget, value):
            if hasattr(widget, "delete") and hasattr(widget, "insert"):
                widget.delete(0, "end")
                widget.insert(0, str(value) if value is not None else "")
            else:
                widget.set(str(value) if value is not None else "")

        _set(self.dumps_var, self.config.get("dumps_dir"))
        _set(self.lastport_var, self.config.get("last_uart_port"))
        _set(self.baud_var, self.config.get("last_uart_baud"))
        _set(self.font_var, self.config.get("font_size") or 11)
        _set(self.theme_var, self.config.get("log_theme"))

    def _on_save_settings(self):
        try:
            self.config.set("dumps_dir", self.dumps_var.get().strip())
            self.config.set("last_uart_port", self.lastport_var.get().strip())
            self.config.set("last_uart_baud", self.baud_var.get().strip())

            font_str = self.font_var.get().strip()
            try:
                font_size = int(font_str)
                if font_size < 6 or font_size > 40:
                    raise ValueError
                self.config.set("font_size", font_size)
            except ValueError:
                messagebox.showerror("Error",
                                     "Font size must be a number between 6 and 40.")
                return

            self.config.set("log_theme", self.theme_var.get().strip())
            self.config.save()

            if self.on_apply_font:
                try:
                    self.on_apply_font(font_size)
                except Exception as e:
                    print(f"[settings] apply font error: {e}", flush=True)

            messagebox.showinfo("Settings", "Settings saved.")
            self.logger.log("[sys] Settings saved")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save: {e}")

    # ---------- Helper ----------
    def _add_row(self, row_idx, label_text, widget):
        ttk.Label(self, text=label_text, width=28, anchor="w").grid(
            row=row_idx, column=0, sticky="w", padx=12, pady=6)
        widget.grid(row=row_idx, column=1, sticky="ew", padx=(0, 12), pady=6)

    # ---------- Log size ----------
    def _refresh_size(self):
        try:
            self.log_size_var.config(state="normal")
            self.log_size_var.delete(0, "end")
            self.log_size_var.insert(0, self.logger.get_size_human())
            self.log_size_var.config(state="readonly")
        except Exception:
            pass

    def _schedule_auto_refresh(self):
        if self._auto_refresh_id is not None:
            try:
                self.root.after_cancel(self._auto_refresh_id)
            except Exception:
                pass
        self._auto_refresh_id = self.root.after(3000, self._auto_refresh_tick)

    def _auto_refresh_tick(self):
        self._auto_refresh_id = None
        self._refresh_size()
        self._schedule_auto_refresh()

    # ---------- Log handlers ----------
    def _on_open_log(self):
        try:
            self.logger.open_in_default()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open log: {e}")

    def _on_clear_log(self):
        ok = messagebox.askyesno(
            "Clear log",
            "Delete the system log file?\n\n"
            "This cannot be undone.",
            icon="warning",
        )
        if not ok:
            return
        try:
            self.logger.clear()
            self._refresh_size()
            self.logger.log("[sys] Log cleared by user")
        except Exception as e:
            messagebox.showerror("Error", f"Could not clear log: {e}")
