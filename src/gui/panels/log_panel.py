"""Log Panel - Color-coded operation log with timestamps."""

from __future__ import annotations
import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCharFormat, QTextCursor, QColor

from ..theme import COLORS

# Color mapping for log levels
LOG_COLORS = {
    "debug":   "#6C7086",
    "info":    "#CDD6F4",
    "warning": "#FAB387",
    "error":   "#F38BA8",
    "success": "#A6E3A1",
    "critical":"#FF4444",
}

LOG_PREFIXES = {
    "debug":   "[DBG]  ",
    "info":    "[INFO] ",
    "warning": "[WARN] ",
    "error":   "[ERR]  ",
    "success": "[OK]   ",
    "critical":"[CRIT] ",
}


class LogPanel(QWidget):
    """Right-side log panel with timestamped, color-coded messages."""

    MAX_LINES = 2000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._min_level = "debug"
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        hdr = QHBoxLayout()
        hdr.setContentsMargins(4, 4, 4, 4)

        lbl = QLabel("Operation Log")
        lbl.setStyleSheet(
            f"color: {COLORS['accent_blue']}; font-size: 10pt; font-weight: 700;"
        )
        hdr.addWidget(lbl)

        hdr.addStretch()

        # Level filter
        self.combo_level = QComboBox()
        self.combo_level.addItems(["All", "Info+", "Warnings+", "Errors"])
        self.combo_level.setMaximumWidth(100)
        self.combo_level.setStyleSheet(f"font-size: 8pt;")
        hdr.addWidget(self.combo_level)

        # Clear button
        btn_clear = QPushButton("Clear")
        btn_clear.setMaximumWidth(55)
        btn_clear.setStyleSheet(f"font-size: 8pt;")
        hdr.addWidget(btn_clear)

        # Auto-scroll toggle
        self.chk_autoscroll = QCheckBox("Auto")
        self.chk_autoscroll.setChecked(True)
        self.chk_autoscroll.setStyleSheet(f"font-size: 8pt; color: {COLORS['fg_muted']};")
        hdr.addWidget(self.chk_autoscroll)

        layout.addLayout(hdr)

        # Text area
        self._text = QPlainTextEdit()
        btn_clear.clicked.connect(self._text.clear)
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(self.MAX_LINES)
        self._text.setFont(QFont("Consolas", 8))
        self._text.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['fg_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
                padding: 4px;
            }}
        """)
        layout.addWidget(self._text, stretch=1)

        # Welcome message
        self.add_message("info", "NAND Flash Clone Tool v1.0.0 started")
        self.add_message("info", "Connect Teensy 4.1 board and click 'Connect'")

    def add_message(self, level: str, message: str):
        """Add a log message with timestamp and color."""
        level = level.lower()
        now   = datetime.datetime.now().strftime("%H:%M:%S.%f")[:12]

        prefix = LOG_PREFIXES.get(level, "[LOG]  ")
        color  = LOG_COLORS.get(level, COLORS["fg_primary"])
        line   = f"{now}  {prefix}{message}"

        # Insert colored text
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(line + "\n")

        if self.chk_autoscroll.isChecked():
            self._text.setTextCursor(cursor)
            self._text.ensureCursorVisible()

    def add_success(self, message: str):
        self.add_message("success", message)

    def save_to_file(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self._text.toPlainText())
