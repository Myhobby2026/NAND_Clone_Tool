"""
Settings & Configuration System
================================
Persistent application settings using QSettings (Windows Registry / .ini file).
Also provides structured logging configuration.
"""

from __future__ import annotations

import os
import logging
import logging.handlers
from typing import Any, Optional

from PyQt6.QtCore import QSettings, QStandardPaths


# ─────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────
APP_NAME    = "NANDFlashCloneTool"
APP_ORG     = "NANDTools"
APP_VERSION = "1.0.0"

SETTINGS_KEYS = {
    # Serial
    "serial/port":             "",
    "serial/baud":             2_000_000,
    "serial/auto_detect":      True,

    # ECC
    "ecc/mode":                "hamming",
    "ecc/auto_select":         True,

    # Operations
    "ops/skip_bad_blocks":     True,
    "ops/verify_after_write":  True,
    "ops/include_oob":         False,

    # UI
    "ui/theme":                "dark",
    "ui/font_size":            10,
    "ui/hex_cols":             16,
    "ui/autoscroll_log":       True,
    "ui/window_geometry":      None,
    "ui/window_state":         None,

    # Paths
    "paths/last_open_dir":     "",
    "paths/last_save_dir":     "",

    # Logging
    "log/level":               "INFO",
    "log/file_enabled":        True,
    "log/max_size_mb":         10,
    "log/backup_count":        3,
}


# ─────────────────────────────────────────────────────────────
#  Settings Class
# ─────────────────────────────────────────────────────────────
class AppSettings:
    """
    Thread-safe application settings wrapper around QSettings.
    Uses Windows Registry on Windows (HKCU\\Software\\NANDTools\\NANDFlashCloneTool).
    """

    _instance: Optional["AppSettings"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._qs = QSettings(APP_ORG, APP_NAME)

    @classmethod
    def instance(cls) -> "AppSettings":
        return cls()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        if default is None:
            default = SETTINGS_KEYS.get(key)
        return self._qs.value(key, default)

    def set(self, key: str, value: Any):
        """Set a setting value."""
        self._qs.setValue(key, value)

    def get_bool(self, key: str) -> bool:
        val = self.get(key)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes")
        return bool(val)

    def get_int(self, key: str) -> int:
        return int(self.get(key, 0) or 0)

    def get_str(self, key: str) -> str:
        return str(self.get(key, "") or "")

    def reset_all(self):
        """Reset all settings to defaults."""
        self._qs.clear()
        for key, default in SETTINGS_KEYS.items():
            if default is not None:
                self._qs.setValue(key, default)

    def sync(self):
        self._qs.sync()

    # Convenience properties
    @property
    def serial_port(self) -> str:
        return self.get_str("serial/port")

    @serial_port.setter
    def serial_port(self, v: str):
        self.set("serial/port", v)

    @property
    def ecc_mode(self) -> str:
        return self.get_str("ecc/mode") or "hamming"

    @ecc_mode.setter
    def ecc_mode(self, v: str):
        self.set("ecc/mode", v)

    @property
    def skip_bad_blocks(self) -> bool:
        return self.get_bool("ops/skip_bad_blocks")

    @skip_bad_blocks.setter
    def skip_bad_blocks(self, v: bool):
        self.set("ops/skip_bad_blocks", v)

    @property
    def verify_after_write(self) -> bool:
        return self.get_bool("ops/verify_after_write")

    @verify_after_write.setter
    def verify_after_write(self, v: bool):
        self.set("ops/verify_after_write", v)

    @property
    def last_open_dir(self) -> str:
        return self.get_str("paths/last_open_dir") or os.path.expanduser("~")

    @last_open_dir.setter
    def last_open_dir(self, v: str):
        self.set("paths/last_open_dir", v)

    @property
    def last_save_dir(self) -> str:
        return self.get_str("paths/last_save_dir") or os.path.expanduser("~")

    @last_save_dir.setter
    def last_save_dir(self, v: str):
        self.set("paths/last_save_dir", v)


# ─────────────────────────────────────────────────────────────
#  Logging Setup
# ─────────────────────────────────────────────────────────────
def get_log_dir() -> str:
    """Return platform-appropriate log directory."""
    data_dir = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    log_dir = os.path.join(data_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def setup_logging(level_name: str = "INFO", enable_file: bool = True) -> logging.Logger:
    """
    Configure application-wide logging.
    
    - Console: DEBUG+ in development, WARNING+ in production
    - File: Rotating log file in AppData\\Roaming\\NANDTools
    """
    level = getattr(logging, level_name.upper(), logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)-24s  %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_fmt)
    root_logger.addHandler(console_handler)

    # File handler (rotating)
    if enable_file:
        log_dir   = get_log_dir()
        log_path  = os.path.join(log_dir, "nand_flash_tool.log")
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes   = 10 * 1024 * 1024,   # 10 MB
            backupCount = 3,
            encoding   = "utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_fmt = logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)-30s  %(message)s"
        )
        file_handler.setFormatter(file_fmt)
        root_logger.addHandler(file_handler)

    logger = logging.getLogger("nand_flash_tool")
    logger.info("Logging initialized: level=%s, file=%s", level_name, enable_file)
    if enable_file:
        logger.info("Log file: %s", os.path.join(get_log_dir(), "nand_flash_tool.log"))

    return logger
