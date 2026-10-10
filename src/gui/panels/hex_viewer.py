"""
Hex Viewer Panel
================
Professional hex viewer for NAND Flash page data.
Displays data in standard hex+ASCII format with:
  - Configurable columns (8/16/32 bytes wide)
  - Address display (hex/decimal)
  - ASCII sidebar
  - Go-to address navigation
  - Search functionality
  - Page navigation for large files
"""

from __future__ import annotations
import os
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QGroupBox, QFrame,
    QScrollArea, QSizePolicy, QPlainTextEdit, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QFontMetrics, QColor, QTextCharFormat, QTextCursor

from ...core.nand_engine import NANDEngine
from ..theme import COLORS


class HexViewerPanel(QWidget):
    """Professional hex viewer for NAND data."""

    CHUNK_SIZE = 4096   # bytes displayed at once

    def __init__(self, engine: NANDEngine = None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._data:       bytes = b""
        self._file_path:  Optional[str] = None
        self._file_size:  int = 0
        self._offset:     int = 0   # current view offset
        self._cols:       int = 16
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # ── Header ────────────────────────────────────────────
        title = QLabel("🔢  Hex Viewer")
        title.setStyleSheet(
            f"color: {COLORS['accent_blue']}; font-size: 14pt; font-weight: 700;"
        )
        layout.addWidget(title)

        # ── Toolbar ───────────────────────────────────────────
        tb_layout = QHBoxLayout()
        tb_layout.setSpacing(8)

        # File path display
        self.lbl_file = QLabel("No file loaded")
        self.lbl_file.setStyleSheet(
            f"color: {COLORS['fg_muted']}; font-size: 9pt; font-style: italic;"
        )
        tb_layout.addWidget(self.lbl_file, stretch=1)

        # Columns
        tb_layout.addWidget(QLabel("Cols:"))
        self.combo_cols = QComboBox()
        self.combo_cols.addItems(["8", "16", "32"])
        self.combo_cols.setCurrentText("16")
        self.combo_cols.setMaximumWidth(60)
        self.combo_cols.currentTextChanged.connect(self._on_cols_changed)
        tb_layout.addWidget(self.combo_cols)

        # Go to address
        tb_layout.addWidget(QLabel("Go to:"))
        self.edit_goto = QLineEdit()
        self.edit_goto.setPlaceholderText("0x0000")
        self.edit_goto.setMaximumWidth(90)
        self.edit_goto.setFont(QFont("Consolas", 9))
        self.edit_goto.returnPressed.connect(self._goto_address)
        tb_layout.addWidget(self.edit_goto)

        btn_goto = QPushButton("→")
        btn_goto.setMaximumWidth(36)
        btn_goto.clicked.connect(self._goto_address)
        tb_layout.addWidget(btn_goto)

        tb_layout.addWidget(QLabel("  "))

        # Search
        self.edit_search = QLineEdit()
        self.edit_search.setPlaceholderText("Search hex (e.g. FF A0 B3)…")
        self.edit_search.setMaximumWidth(200)
        self.edit_search.setFont(QFont("Consolas", 9))
        tb_layout.addWidget(self.edit_search)

        btn_search = QPushButton("🔍")
        btn_search.setMaximumWidth(36)
        btn_search.clicked.connect(self._search)
        tb_layout.addWidget(btn_search)

        layout.addLayout(tb_layout)

        # ── Page navigation ───────────────────────────────────
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(6)

        self.btn_first = QPushButton("⏮")
        self.btn_prev  = QPushButton("◀ Prev")
        self.btn_next  = QPushButton("Next ▶")
        self.btn_last  = QPushButton("⏭")

        for btn in (self.btn_first, self.btn_prev, self.btn_next, self.btn_last):
            btn.setMaximumWidth(80)

        self.btn_first.clicked.connect(lambda: self._goto_offset(0))
        self.btn_prev.clicked.connect(self._prev_chunk)
        self.btn_next.clicked.connect(self._next_chunk)
        self.btn_last.clicked.connect(self._last_chunk)

        nav_layout.addWidget(self.btn_first)
        nav_layout.addWidget(self.btn_prev)

        self.lbl_pos = QLabel("0x000000  (0 / 0 bytes)")
        self.lbl_pos.setStyleSheet(
            f"color: {COLORS['fg_muted']}; font-family: Consolas; font-size: 9pt;"
        )
        nav_layout.addWidget(self.lbl_pos, stretch=1)

        nav_layout.addWidget(self.btn_next)
        nav_layout.addWidget(self.btn_last)

        # Load page from chip
        self.spin_page = QSpinBox()
        self.spin_page.setMinimum(0)
        self.spin_page.setMaximum(9999999)
        self.spin_page.setPrefix("Page ")
        self.spin_page.setMaximumWidth(110)
        nav_layout.addWidget(self.spin_page)

        self.btn_load_page = QPushButton("Load Page")
        self.btn_load_page.setObjectName("btn_primary")
        self.btn_load_page.setMaximumWidth(90)
        self.btn_load_page.clicked.connect(self._load_chip_page)
        nav_layout.addWidget(self.btn_load_page)

        layout.addLayout(nav_layout)

        # ── Hex Display ───────────────────────────────────────
        self.hex_display = QPlainTextEdit()
        self.hex_display.setReadOnly(True)
        self.hex_display.setFont(QFont("Consolas", 10))
        self.hex_display.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.hex_display.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['fg_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10pt;
            }}
        """)
        layout.addWidget(self.hex_display, stretch=1)

        # ── Info Bar ──────────────────────────────────────────
        info_layout = QHBoxLayout()
        self.lbl_sel_info = QLabel("Click a byte to inspect")
        self.lbl_sel_info.setStyleSheet(
            f"color: {COLORS['fg_muted']}; font-family: Consolas; font-size: 9pt;"
        )
        info_layout.addWidget(self.lbl_sel_info, stretch=1)

        self.lbl_file_size = QLabel("Size: --")
        self.lbl_file_size.setStyleSheet(
            f"color: {COLORS['fg_muted']}; font-size: 9pt;"
        )
        info_layout.addWidget(self.lbl_file_size)
        layout.addLayout(info_layout)

        # Initialize display
        self._render()

    def connect_engine(self, engine: NANDEngine):
        self.engine = engine

    def load_file(self, path: str):
        """Load a binary file for hex viewing."""
        try:
            self._file_path = path
            self._file_size = os.path.getsize(path)
            self._offset    = 0
            self.lbl_file.setText(os.path.basename(path))
            self.lbl_file_size.setText(
                f"Size: {self._file_size:,} bytes  ({self._file_size // 1024} KB)"
            )
            self._load_chunk(0)
        except OSError as e:
            self.lbl_file.setText(f"Error: {e}")

    def load_bytes(self, data: bytes, label: str = ""):
        """Load bytes directly."""
        self._file_path = None
        self._data      = data
        self._file_size = len(data)
        self._offset    = 0
        self.lbl_file.setText(label or f"{len(data):,} bytes")
        self.lbl_file_size.setText(f"Size: {self._file_size:,} bytes")
        self._render()

    def _load_chunk(self, offset: int):
        if not self._file_path:
            return
        self._offset = offset
        try:
            with open(self._file_path, "rb") as f:
                f.seek(offset)
                self._data = f.read(self.CHUNK_SIZE)
            self._render()
        except OSError as e:
            self.hex_display.setPlainText(f"Error reading file: {e}")

    def _render(self):
        """Render hex+ASCII display."""
        if not self._data:
            self.hex_display.setPlainText("No data loaded.\n\nUse File → Open to load a dump file,\nor use 'Load Page' to read from the chip.")
            return

        cols = self._cols
        lines = []
        lines.append(
            f"{'Offset':<10}"
            + "  "
            + "  ".join(f"{i:02X}" for i in range(cols))
            + "   "
            + "".join(f"{i:X}" for i in range(min(cols, 16)))
        )
        lines.append("─" * (10 + 2 + cols * 3 + 3 + min(cols, 16) + 4))

        for row_start in range(0, len(self._data), cols):
            chunk = self._data[row_start: row_start + cols]
            addr  = self._offset + row_start

            hex_part = "  ".join(f"{b:02X}" for b in chunk)
            hex_part = hex_part.ljust(cols * 3 - 1)

            ascii_part = "".join(
                chr(b) if 32 <= b < 127 else "." for b in chunk
            )

            lines.append(f"0x{addr:08X}  {hex_part}   {ascii_part}")

        self.hex_display.setPlainText("\n".join(lines))

        # Update position label
        end = min(self._offset + len(self._data), self._file_size)
        self.lbl_pos.setText(
            f"0x{self._offset:08X} – 0x{end:08X}  "
            f"({self._offset:,} – {end:,} / {self._file_size:,} bytes)"
        )

    def _on_cols_changed(self, text: str):
        try:
            self._cols = int(text)
            self._render()
        except ValueError:
            pass

    def _goto_address(self):
        text = self.edit_goto.text().strip()
        try:
            addr = int(text, 16) if text.startswith("0x") else int(text)
            self._goto_offset(addr)
        except ValueError:
            pass

    def _goto_offset(self, offset: int):
        offset = max(0, min(offset, self._file_size - 1))
        # Align to chunk boundary
        aligned = (offset // self.CHUNK_SIZE) * self.CHUNK_SIZE
        if self._file_path:
            self._load_chunk(aligned)
        else:
            self._offset = aligned
            self._render()

    def _prev_chunk(self):
        self._goto_offset(max(0, self._offset - self.CHUNK_SIZE))

    def _next_chunk(self):
        if self._offset + self.CHUNK_SIZE < self._file_size:
            self._goto_offset(self._offset + self.CHUNK_SIZE)

    def _last_chunk(self):
        last = ((self._file_size - 1) // self.CHUNK_SIZE) * self.CHUNK_SIZE
        self._goto_offset(last)

    def _search(self):
        """Search for hex pattern in loaded data."""
        text = self.edit_search.text().strip()
        if not text:
            return
        try:
            pattern = bytes(int(h, 16) for h in text.split())
        except ValueError:
            self.lbl_sel_info.setText("⚠ Invalid hex pattern")
            return

        idx = self._data.find(pattern)
        if idx < 0:
            self.lbl_sel_info.setText(f"Pattern not found in current view")
        else:
            abs_addr = self._offset + idx
            self.lbl_sel_info.setText(
                f"Found at 0x{abs_addr:08X} (offset +{idx})"
            )

    def _load_chip_page(self):
        """Read a single page from the chip and display it."""
        if not self.engine or not self.engine.serial.connected:
            self.lbl_sel_info.setText("⚠ Not connected")
            return
        page_num = self.spin_page.value()
        raw = self.engine.read_single_page(page_num)
        if raw:
            self.load_bytes(raw, f"Page {page_num}")
            self.lbl_sel_info.setText(f"Page {page_num} loaded ({len(raw)} bytes)")
        else:
            self.lbl_sel_info.setText(f"⚠ Failed to read page {page_num}")
