"""
Block Map Panel
===============
Visual block map showing good/bad/erased/written block states
as a grid of colored tiles.
"""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSlot, QRect, QSize
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QFontMetrics

from ...core.nand_engine import NANDEngine
from ...models.nand_models import DeviceInfo
from ..theme import COLORS


# Block state colors
STATE_COLORS = {
    "unknown": "#45475A",
    "good":    "#40A02B",
    "bad":     "#D20F39",
    "written": "#1E66F5",
    "erased":  "#A6E3A1",
    "reading": "#FAB387",
}


class BlockMapWidget(QWidget):
    """Custom widget that paints a grid of block state tiles."""

    TILE_SIZE = 10   # pixels per tile
    TILE_GAP  = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._states:    dict[int, str] = {}  # block_num → state
        self._total:     int = 0
        self._hover_blk: int = -1
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_total(self, n: int):
        self._total = n
        self._states = {}
        self.update()

    def set_block_state(self, block: int, state: str):
        self._states[block] = state
        self.update()

    def set_bad_blocks(self, bad_list: list[int]):
        for blk in bad_list:
            self._states[blk] = "bad"
        self.update()

    def _tile_size(self) -> int:
        return self.TILE_SIZE + self.TILE_GAP

    def _cols(self) -> int:
        if self._tile_size() == 0:
            return 1
        return max(1, self.width() // self._tile_size())

    def sizeHint(self) -> QSize:
        if self._total == 0:
            return QSize(400, 200)
        cols = max(1, 400 // self._tile_size())
        rows = (self._total + cols - 1) // cols
        return QSize(400, rows * self._tile_size() + 4)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        ts = self.TILE_SIZE
        gs = self.TILE_GAP
        full = ts + gs
        cols = self._cols()

        for blk in range(self._total):
            row = blk // cols
            col = blk % cols
            x   = col * full + gs
            y   = row * full + gs

            state = self._states.get(blk, "unknown")
            color = QColor(STATE_COLORS.get(state, STATE_COLORS["unknown"]))

            if blk == self._hover_blk:
                color = color.lighter(140)

            painter.fillRect(x, y, ts, ts, color)

        painter.end()

    def mouseMoveEvent(self, event):
        cols = self._cols()
        full = self.TILE_SIZE + self.TILE_GAP
        col  = event.pos().x() // full
        row  = event.pos().y() // full
        blk  = row * cols + col
        if 0 <= blk < self._total:
            self._hover_blk = blk
            state = self._states.get(blk, "unknown")
            self.setToolTip(f"Block {blk}  [{state}]")
        else:
            self._hover_blk = -1
        self.update()

    def leaveEvent(self, event):
        self._hover_blk = -1
        self.update()


class BlockMapPanel(QWidget):
    """Block map panel (full or mini version)."""

    def __init__(self, engine: NANDEngine = None, mini: bool = False, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.mini   = mini
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if not self.mini:
            title = QLabel("▦  Block Map")
            title.setStyleSheet(
                f"color: {COLORS['accent_blue']}; font-size: 14pt; font-weight: 700;"
                f"padding: 12px 16px 4px 16px;"
            )
            layout.addWidget(title)

        # Legend
        legend_layout = QHBoxLayout()
        legend_layout.setContentsMargins(6, 2, 6, 2)
        legend_layout.setSpacing(12)

        def legend_item(color: str, label: str):
            h = QHBoxLayout()
            h.setSpacing(4)
            sq = QFrame()
            sq.setFixedSize(12, 12)
            sq.setStyleSheet(
                f"background-color: {color}; border-radius: 2px; border: none;"
            )
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {COLORS['fg_muted']}; font-size: 8pt;")
            h.addWidget(sq)
            h.addWidget(lbl)
            w = QWidget()
            w.setLayout(h)
            return w

        legend_layout.addWidget(legend_item(STATE_COLORS["good"],    "Good"))
        legend_layout.addWidget(legend_item(STATE_COLORS["bad"],     "Bad"))
        legend_layout.addWidget(legend_item(STATE_COLORS["written"], "Written"))
        legend_layout.addWidget(legend_item(STATE_COLORS["erased"],  "Erased"))
        legend_layout.addWidget(legend_item(STATE_COLORS["unknown"], "Unknown"))
        legend_layout.addStretch()
        layout.addLayout(legend_layout)

        # Map widget in scroll area
        self.map_widget = BlockMapWidget()
        scroll = QScrollArea()
        scroll.setWidget(self.map_widget)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {COLORS['border']}; border-radius: 4px; }}"
        )
        layout.addWidget(scroll, stretch=1)

        # Stats (full mode only)
        if not self.mini:
            stats_layout = QHBoxLayout()
            stats_layout.setContentsMargins(8, 4, 8, 4)
            self.lbl_stats = QLabel("No device detected")
            self.lbl_stats.setStyleSheet(
                f"color: {COLORS['fg_muted']}; font-size: 9pt;"
            )
            stats_layout.addWidget(self.lbl_stats)
            layout.addLayout(stats_layout)

    def connect_engine(self, engine: NANDEngine):
        self.engine = engine
        engine.device_detected.connect(self._on_device_detected)
        engine.bad_block_found.connect(self._on_bad_block)

    @pyqtSlot(DeviceInfo)
    def _on_device_detected(self, dev: DeviceInfo):
        self.map_widget.set_total(dev.total_blocks)
        if not self.mini and hasattr(self, "lbl_stats"):
            self.lbl_stats.setText(
                f"{dev.total_blocks:,} blocks  "
                f"| {dev.page_size}B pages  "
                f"| {dev.pages_per_block} pages/block"
            )

    @pyqtSlot(int)
    def _on_bad_block(self, block: int):
        self.map_widget.set_block_state(block, "bad")

    def mark_block(self, block: int, state: str):
        self.map_widget.set_block_state(block, state)
