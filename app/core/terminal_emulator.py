"""
Terminal emulator for UART.

Uses pyte.HistoryScreen (with scrollback) + pyserial.
Supports dynamic resize.
"""

import threading
from typing import Callable, Dict, List, Optional

import pyte
import serial


MAX_HISTORY_LINES = 1000


class TerminalEmulator:
    """Terminal with scrollback and resize support."""

    def __init__(self, cols: int = 120, rows: int = 30,
                 history: int = MAX_HISTORY_LINES):
        self.cols = cols
        self.rows = rows
        self.history_size = history

        self.screen = pyte.HistoryScreen(cols, rows, history=history)
        self.stream = pyte.Stream(self.screen)

        self.serial: Optional[serial.Serial] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_reader = threading.Event()
        self._closing = False

        self.on_update: Optional[Callable[[], None]] = None
        self.on_disconnect: Optional[Callable[[str], None]] = None

    # ---------- State ----------
    def is_open(self) -> bool:
        return self.serial is not None and self.serial.is_open

    def get_port_name(self) -> Optional[str]:
        return self.serial.port if self.serial else None

    def get_size(self):
        return self.cols, self.rows

    # ---------- Resize ----------
    def resize(self, cols: int, rows: int):
        """Resize the virtual screen and send resize escape to the device."""
        if cols < 20 or rows < 5:
            return
        if cols == self.cols and rows == self.rows:
            return

        self.cols = cols
        self.rows = rows

        old_history = []
        try:
            old_history = list(self.screen.history.top)
        except Exception:
            pass

        self.screen = pyte.HistoryScreen(cols, rows, history=self.history_size)
        self.stream = pyte.Stream(self.screen)

        if old_history:
            try:
                for row in old_history[-self.history_size:]:
                    self.screen.history.top.append(row)
            except Exception:
                pass

        if self.is_open():
            try:
                seq = f"\x1b[8;{rows};{cols}t"
                self.send(seq.encode("ascii", errors="replace"))
            except Exception:
                pass

    # ---------- Open / close ----------
    def open(self, port: str, baudrate: int = 115200,
             on_update: Callable[[], None] = None,
             on_disconnect: Callable[[str], None] = None):
        if self.is_open():
            raise RuntimeError("Port already open")

        self.on_update = on_update
        self.on_disconnect = on_disconnect
        self._closing = False

        self.serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.05,
        )

        self._stop_reader.clear()
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def close(self):
        self._closing = True
        self._stop_reader.set()
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)
        if self.serial:
            try:
                self.serial.close()
            except Exception:
                pass
            self.serial = None
        self._reader_thread = None
        self._closing = False

    def _reader_loop(self):
        while not self._stop_reader.is_set():
            port = self.serial
            if port is None:
                break
            try:
                if not port.is_open:
                    break
                data = port.read(4096)
                if data:
                    text = data.decode("utf-8", errors="replace")
                    try:
                        self.stream.feed(text)
                    except Exception as e:
                        print(f"[terminal] stream error: {e}", flush=True)
                    if self.on_update:
                        try:
                            self.on_update()
                        except Exception as e:
                            print(f"[terminal] on_update error: {e}", flush=True)
            except serial.SerialException as e:
                if not self._closing and self.on_disconnect:
                    try:
                        self.on_disconnect(str(e))
                    except Exception:
                        pass
                break
            except OSError:
                break
            except Exception as e:
                print(f"[terminal] read error: {e}", flush=True)
                break
        if not self._closing:
            self.serial = None

    # ---------- Send ----------
    def send(self, data: bytes):
        if not self.is_open():
            raise RuntimeError("Port not open")
        self.serial.write(data)
        self.serial.flush()

    def send_key(self, key: str):
        if not key:
            return
        self.send(key.encode("utf-8", errors="replace"))

    # ---------- Line assembly ----------
    def _row_dict_to_str(self, row: Dict[int, "pyte.screens.Char"]) -> str:
        chars = []
        for x in range(self.cols):
            ch = row.get(x)
            if ch is None:
                chars.append(" ")
            else:
                chars.append(ch.data if ch.data else " ")
        return "".join(chars).rstrip()

    def _buffer_line_to_str(self, y: int) -> str:
        try:
            row = self.screen.buffer.get(y, {})
            return self._row_dict_to_str(row)
        except Exception:
            return ""

    def get_lines(self) -> List[str]:
        lines = []
        try:
            for row in self.screen.history.top:
                lines.append(self._row_dict_to_str(row))
            for y in range(self.rows):
                lines.append(self._buffer_line_to_str(y))
        except Exception as e:
            print(f"[terminal] get_lines error: {e}", flush=True)
        return lines

    def get_cursor(self):
        try:
            return self.screen.cursor.x, self.screen.cursor.y
        except Exception:
            return 0, 0

    def get_history_offset(self) -> int:
        try:
            return len(self.screen.history.top)
        except Exception:
            return 0
