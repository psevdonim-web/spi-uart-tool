"""
Application configuration storage.

Path: ~/Library/Application Support/SPI-UART-Tool/config.json
Format: JSON
"""

import json
import os
from typing import Any, Dict


CONFIG_DIR = os.path.expanduser("~/Library/Application Support/SPI-UART-Tool")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


DEFAULTS = {
    "dumps_dir": "~/Documents/SPI_UART_Tool/dumps",
    "last_uart_port": "",
    "last_uart_baud": "115200",
    "log_theme": "system",
    "font_size": 11,
}


class Config:
    """Simple JSON config."""

    def __init__(self):
        self.data: Dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self):
        """Load config from file. Missing file -> defaults remain."""
        if not os.path.isfile(CONFIG_PATH):
            return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except Exception:
            # corrupted config — ignore
            pass

    def save(self):
        """Save config to file."""
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[config] Could not save: {e}", flush=True)

    def get(self, key: str, default: Any = None) -> Any:
        if default is not None:
            return self.data.get(key, default)
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: Any):
        self.data[key] = value
