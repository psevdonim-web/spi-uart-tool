"""
UART port management via pyserial.

Features:
- list available ports (without Bluetooth)
- open / close port
- send data
- receive data in a background thread (via callback)
"""

import threading
from typing import Callable, List, Optional

import serial
import serial.tools.list_ports


class UartManager:
    """pyserial wrapper. One instance per application."""

    def __init__(self):
        self._port: Optional[serial.Serial] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_reader = threading.Event()
        self._closing = False
        self._on_data: Optional[Callable[[bytes], None]] = None
        self._on_disconnect: Optional[Callable[[str], None]] = None

    # ---------- Ports ----------
    @staticmethod
    def list_ports() -> List[str]:
        result = []
        for p in serial.tools.list_ports.comports():
            device = p.device
            if "Bluetooth" in device or "debug-console" in device:
                continue
            result.append(device)
        return sorted(result)

    # ---------- State ----------
    def is_open(self) -> bool:
        return self._port is not None and self._port.is_open

    def get_port_name(self) -> Optional[str]:
        if self._port:
            return self._port.port
        return None

    # ---------- Open / close ----------
    def open(self, port: str, baudrate: int = 115200,
             on_data: Callable[[bytes], None] = None,
             on_disconnect: Callable[[str], None] = None):
        if self.is_open():
            raise RuntimeError("Port already open")

        self._on_data = on_data
        self._on_disconnect = on_disconnect
        self._closing = False

        self._port = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )

        self._stop_reader.clear()
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def close(self):
        """Close port. Does NOT call on_disconnect."""
        self._closing = True
        self._stop_reader.set()

        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)

        if self._port:
            try:
                self._port.close()
            except Exception:
                pass
            self._port = None

        self._reader_thread = None
        self._closing = False

    # ---------- Send ----------
    def send(self, data: bytes):
        if not self.is_open():
            raise RuntimeError("Port not open")
        self._port.write(data)
        self._port.flush()

    def send_text(self, text: str, add_crlf: bool = True):
        if add_crlf:
            text = text + "\r\n"
        self.send(text.encode("utf-8", errors="replace"))

    # ---------- Receive ----------
    def _reader_loop(self):
        while not self._stop_reader.is_set():
            port = self._port
            if port is None:
                break
            try:
                if not port.is_open:
                    break
                data = port.read(4096)
                if data and self._on_data:
                    try:
                        self._on_data(data)
                    except Exception as e:
                        print(f"[uart_manager] on_data error: {e}", flush=True)
            except serial.SerialException as e:
                if not self._closing and self._on_disconnect:
                    try:
                        self._on_disconnect(str(e))
                    except Exception:
                        pass
                break
            except OSError:
                break
            except Exception as e:
                print(f"[uart_manager] read error: {e}", flush=True)
                break

        if not self._closing:
            self._port = None
