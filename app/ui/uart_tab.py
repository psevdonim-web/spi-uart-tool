"""
UART tab: terminal (pyte + pyserial) for device communication.
"""

import os
import subprocess
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .common import (
    LOG_BG, LOG_FG, LOG_SEL_BG,
    attach_text_context_menu, make_tooltip,
)
from .terminal_widget import TerminalWidget
from ..core.uart_manager import UartManager
from ..core.terminal_emulator import TerminalEmulator


LOG_DIR = os.path.expanduser("~/Documents/SPI_UART_Tool/uart-logs")


def get_port_process(port: str):
    """Return (pid, name) of the process holding the port, or (None, None)."""
    try:
        out = subprocess.run(
            ["lsof", "-t", port],
            capture_output=True, text=True, timeout=2
        )
        pids = out.stdout.strip().split()
        if not pids:
            return None, None
        pid = pids[0]
        out2 = subprocess.run(
            ["ps", "-p", pid, "-o", "comm="],
            capture_output=True, text=True, timeout=2
        )
        name = out2.stdout.strip() or "?"
        return pid, name
    except Exception:
        return None, None


def kill_port_process(pid: str) -> bool:
    """Kill process by PID. Return True on success."""
    try:
        subprocess.run(["kill", pid], timeout=2)
        return True
    except Exception:
        try:
            subprocess.run(["kill", "-9", pid], timeout=2)
            return True
        except Exception:
            return False


class UartTab(ttk.Frame):
    """UART tab with terminal."""

    def __init__(self, parent, root, logger, config):
        super().__init__(parent)
        self.root = root
        self.logger = logger
        self.config = config

        self.terminal = TerminalEmulator(cols=120, rows=30)
        self.connected = False

        try:
            font_size = int(self.config.get("font_size") or 11)
        except (ValueError, TypeError):
            font_size = 11

        # ---------- Top: port, baud, connect, clear ----------
        top = ttk.Frame(self)
        top.pack(side="top", fill="x")

        port_row = ttk.Frame(top)
        port_row.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Label(port_row, text="Port:").pack(side="left")

        self.port_var = tk.StringVar(value="")
        self.port_combo = ttk.Combobox(
            port_row, textvariable=self.port_var,
            values=[], width=28)
        self.port_combo.pack(side="left", padx=6)

        self.btn_refresh = ttk.Button(port_row, text="Refresh",
                                      command=self._on_refresh_click)
        self.btn_refresh.pack(side="left", padx=4)

        ttk.Label(port_row, text="Baud:").pack(side="left", padx=(20, 4))

        saved_baud = self.config.get("last_uart_baud") or "115200"
        self.baud_var = tk.StringVar(value=saved_baud)
        self.baud_combo = ttk.Combobox(
            port_row, textvariable=self.baud_var,
            values=["9600", "19200", "38400", "57600", "115200",
                    "230400", "460800", "921600"],
            width=10)
        self.baud_combo.pack(side="left")

        self.btn_connect = ttk.Button(port_row, text="Connect",
                                      command=self._on_connect_click)
        self.btn_connect.pack(side="left", padx=8)

        self.btn_clear = ttk.Button(port_row, text="Clear",
                                    command=self._on_clear_click)
        self.btn_clear.pack(side="left", padx=4)

        # ---------- Terminal ----------
        term_frame = ttk.LabelFrame(self, text="Terminal")
        term_frame.pack(side="top", fill="both", expand=True, padx=12, pady=6)

        self.term_widget = TerminalWidget(
            term_frame,
            on_key=self._on_terminal_key,
            on_resize=self._on_terminal_resize,
            font_size=font_size,
        )
        self.term_widget.pack(fill="both", expand=True, padx=4, pady=4)

        # ---------- Bottom row ----------
        bottom = ttk.Frame(self)
        bottom.pack(side="bottom", fill="x", padx=12, pady=(0, 6))

        self.btn_save_log = ttk.Button(bottom, text="Save log",
                                       command=self._on_save_log_click)
        self.btn_save_log.pack(side="left", padx=(0, 4))

        self.btn_external = ttk.Button(bottom, text="Open in external terminal",
                                       command=self._on_external_click)
        self.btn_external.pack(side="left", padx=4)

        self.btn_release = ttk.Button(bottom, text="Release port",
                                      command=self._on_release_port_click)
        self.btn_release.pack(side="left", padx=4)
        self.btn_release.config(state="disabled")

        self.status_var = tk.StringVar(value="Not connected")
        ttk.Label(bottom, textvariable=self.status_var,
                  anchor="e", foreground="#808080").pack(side="right")

        self._refresh_ports()
        saved_port = self.config.get("last_uart_port") or ""
        if saved_port and saved_port in (self.port_combo["values"] or []):
            self.port_var.set(saved_port)

        self._refresh_terminal()
        self._check_port_on_start()

    # ---------- Port check on startup ----------
    def _check_port_on_start(self):
        try:
            ports = UartManager.list_ports()
            busy = []
            for p in ports:
                pid, name = get_port_process(p)
                if pid:
                    busy.append((p, pid, name))
            if busy:
                lines = [f"{p} — {name} (PID {pid})" for p, pid, name in busy]
                self.logger.log("[sys] Busy ports: " + "; ".join(lines))
                self.status_var.set(f"Port busy: {busy[0][2]}")
                self.btn_release.config(state="normal")
            else:
                self.btn_release.config(state="disabled")
        except Exception as e:
            self.logger.log(f"[err] Port check: {e}")

    # ---------- Public ----------
    def set_font_size(self, size: int):
        self.term_widget.set_font_size(size)

    # ---------- Ports ----------
    def _refresh_ports(self):
        ports = UartManager.list_ports()
        self.port_combo.config(values=ports)
        if ports and not self.port_var.get():
            saved = self.config.get("last_uart_port") or ""
            if saved and saved in ports:
                self.port_var.set(saved)
            else:
                self.port_var.set(ports[0])

    def _on_refresh_click(self):
        self._refresh_ports()
        ports = UartManager.list_ports()
        self.logger.log(f"[sys] Ports found: {len(ports)}")
        self._check_port_on_start()

    # ---------- Release port ----------
    def _on_release_port_click(self):
        port = self.port_var.get().strip()
        if not port:
            return
        pid, name = get_port_process(port)
        if not pid:
            self.logger.log(f"[sys] Port {port} is free.")
            self.btn_release.config(state="disabled")
            return
        ok = messagebox.askyesno(
            "Release port",
            f"Port {port} is held by process:\n{name} (PID {pid})\n\nKill process?",
            icon="warning",
        )
        if not ok:
            return
        if kill_port_process(pid):
            self.logger.log(f"[sys] Process {name} (PID {pid}) killed.")
            self.status_var.set(f"Port {port} released.")
            self.btn_release.config(state="disabled")
        else:
            self.logger.log(f"[err] Could not kill process {pid}.")

    # ---------- Connect / disconnect ----------
    def _on_connect_click(self):
        if self.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port = self.port_var.get().strip()
        if not port:
            self.logger.log("[err] No port selected.")
            return

        pid, name = get_port_process(port)
        if pid:
            self.logger.log(f"[err] Port {port} is held by {name} (PID {pid}).")
            self.status_var.set(f"Port busy: {name}")
            self.btn_release.config(state="normal")
            messagebox.showerror(
                "Port busy",
                f"Port {port} is held by:\n{name} (PID {pid})\n\n"
                f"Close the process or press 'Release port'.",
            )
            return

        try:
            baud = int(self.baud_var.get().strip())
        except ValueError:
            self.logger.log("[err] Invalid baud rate.")
            return

        try:
            self.terminal.open(
                port=port,
                baudrate=baud,
                on_update=self._on_terminal_update,
                on_disconnect=self._on_terminal_disconnect,
            )
        except Exception as e:
            self.logger.log(f"[err] Could not open port: {e}")
            return

        self.connected = True
        self.btn_connect.config(text="Disconnect")
        self.port_combo.config(state="disabled")
        self.baud_combo.config(state="disabled")
        self.status_var.set(f"Connected: {port} @ {baud}")
        self.logger.log(f"[sys] Connected: {port} @ {baud}")

        self.term_widget.focus_terminal()

        try:
            self.config.set("last_uart_port", port)
            self.config.set("last_uart_baud", str(baud))
            self.config.save()
        except Exception:
            pass

    def _disconnect(self):
        try:
            self.terminal.close()
        except Exception as e:
            self.logger.log(f"[err] Close error: {e}")

        self.connected = False
        self.btn_connect.config(text="Connect")
        self.port_combo.config(state="normal")
        self.baud_combo.config(state="normal")
        self.status_var.set("Not connected")
        self.logger.log("[sys] Disconnected.")

    # ---------- Terminal ----------
    def _on_terminal_update(self):
        self.root.after(0, self._refresh_terminal)

    def _refresh_terminal(self):
        lines = self.terminal.get_lines()
        cx, cy = self.terminal.get_cursor()
        offset = self.terminal.get_history_offset()
        self.term_widget.render(lines, cx, cy, offset)

    def _on_terminal_resize(self, cols, rows):
        try:
            self.terminal.resize(cols, rows)
        except Exception as e:
            self.logger.log(f"[err] Resize error: {e}")

    def _on_terminal_disconnect(self, err: str):
        self.root.after(0, lambda: self._handle_disconnect(err))

    def _handle_disconnect(self, err: str):
        self.connected = False
        self.btn_connect.config(text="Connect")
        self.port_combo.config(state="normal")
        self.baud_combo.config(state="normal")
        self.status_var.set(f"Device disconnected: {err}")
        self.logger.log(f"[err] Device disconnected: {err}")

    def _on_terminal_key(self, data: str):
        if not self.connected:
            return
        try:
            self.terminal.send_key(data)
        except Exception as e:
            self.logger.log(f"[err] Send error: {e}")

    # ---------- Clear ----------
    def _on_clear_click(self):
        try:
            self.terminal.screen.reset()
        except Exception:
            pass
        self._refresh_terminal()

    # ---------- Save log ----------
    def _on_save_log_click(self):
        lines = self.terminal.get_lines()
        text = "\n".join(lines)
        if not text.strip():
            self.logger.log("[err] Log is empty.")
            return

        os.makedirs(LOG_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        default_name = f"uart_{ts}.log"

        out_path = filedialog.asksaveasfilename(
            title="Save UART log",
            initialdir=LOG_DIR,
            initialfile=default_name,
            defaultextension=".log",
            filetypes=[("Logs", "*.log"), ("Text files", "*.txt"),
                       ("All files", "*.*")],
        )
        if not out_path:
            return

        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            self.logger.log(f"[ok] Log saved: {out_path}")
        except Exception as e:
            self.logger.log(f"[err] Could not save: {e}")

    # ---------- External terminal ----------
    def _on_external_click(self):
        port = self.port_var.get().strip()
        if not port:
            self.logger.log("[err] No port selected.")
            return
        try:
            baud = int(self.baud_var.get().strip())
        except ValueError:
            self.logger.log("[err] Invalid baud rate.")
            return

        screen_cmd = f"screen {port} {baud}"
        applescript = (
            f'tell application "Terminal" to do script "{screen_cmd}"\n'
            f'tell application "Terminal" to activate'
        )
        try:
            subprocess.Popen(["osascript", "-e", applescript])
            self.logger.log(f"[sys] Opened in external terminal: {screen_cmd}")
        except Exception as e:
            self.logger.log(f"[err] Could not open: {e}")
