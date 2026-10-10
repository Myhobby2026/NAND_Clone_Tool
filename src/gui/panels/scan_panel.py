"""Scan Bad Blocks Panel - Scan and display NAND bad block information."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor

from ...core.nand_engine import NANDEngine
from ...models.nand_models import OperationProgress, OperationStatus, OperationType
from ..theme import COLORS


class ScanBadBlocksPanel(QWidget):
    def __init__(self, engine: NANDEngine = None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("🔍  Scan Bad Blocks")
        title.setStyleSheet(
            f"color: {COLORS['accent_orange2']}; font-size: 14pt; font-weight: 700;"
        )
        layout.addWidget(title)

        desc = QLabel(
            "Scan all blocks on the NAND Flash chip to identify bad blocks. "
            "Results are used to skip bad blocks during read/write operations."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLORS['fg_muted']}; font-size: 9pt;")
        layout.addWidget(desc)

        # Stats row
        stats_frame = QFrame()
        stats_frame.setStyleSheet(
            f"background-color: {COLORS['bg_secondary']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 6px;"
        )
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(16, 10, 16, 10)

        def stat_widget(label, init="--"):
            w = QWidget()
            vl = QVBoxLayout(w)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(2)
            v = QLabel(init)
            v.setStyleSheet(
                f"color: {COLORS['accent_green2']}; font-size: 14pt; font-weight: 700;"
                f"font-family: 'Consolas', monospace;"
            )
            v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l = QLabel(label)
            l.setStyleSheet(f"color: {COLORS['fg_muted']}; font-size: 8pt;")
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vl.addWidget(v)
            vl.addWidget(l)
            return w, v

        w, self.val_total   = stat_widget("Total Blocks")
        stats_layout.addWidget(w)
        stats_layout.addWidget(QFrame(frameShape=QFrame.Shape.VLine,
                                      styleSheet=f"color: {COLORS['border']};"))

        w, self.val_good    = stat_widget("Good Blocks")
        stats_layout.addWidget(w)
        stats_layout.addWidget(QFrame(frameShape=QFrame.Shape.VLine,
                                      styleSheet=f"color: {COLORS['border']};"))

        w, self.val_bad     = stat_widget("Bad Blocks")
        self.val_bad.setStyleSheet(
            f"color: {COLORS['accent_red2']}; font-size: 14pt; font-weight: 700;"
            f"font-family: 'Consolas', monospace;"
        )
        stats_layout.addWidget(w)
        stats_layout.addWidget(QFrame(frameShape=QFrame.Shape.VLine,
                                      styleSheet=f"color: {COLORS['border']};"))

        w, self.val_percent = stat_widget("Bad %")
        self.val_percent.setStyleSheet(
            f"color: {COLORS['accent_orange2']}; font-size: 14pt; font-weight: 700;"
            f"font-family: 'Consolas', monospace;"
        )
        stats_layout.addWidget(w)
        layout.addWidget(stats_frame)

        # Table
        tbl_grp = QGroupBox("Bad Block List")
        tbl_layout = QVBoxLayout(tbl_grp)
        tbl_layout.setContentsMargins(8, 12, 8, 8)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Block #", "Page Addr.", "Type"])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        tbl_layout.addWidget(self.table)
        layout.addWidget(tbl_grp)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(sep)

        btn_row = QHBoxLayout()

        self.btn_scan = QPushButton("🔍  Scan All Blocks")
        self.btn_scan.setObjectName("btn_warning")
        self.btn_scan.setMinimumWidth(160)
        self.btn_scan.setMinimumHeight(36)
        self.btn_scan.clicked.connect(self._start_scan)
        btn_row.addWidget(self.btn_scan)

        self.btn_cancel = QPushButton("⬛  Cancel")
        self.btn_cancel.setObjectName("btn_danger")
        self.btn_cancel.setMinimumWidth(100)
        self.btn_cancel.setMinimumHeight(36)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(lambda: self.engine and self.engine.cancel_operation())
        btn_row.addWidget(self.btn_cancel)

        btn_row.addStretch()

        self.lbl_status = QLabel("Not scanned yet")
        self.lbl_status.setStyleSheet(f"color: {COLORS['fg_muted']}; font-size: 9pt;")
        btn_row.addWidget(self.lbl_status)
        layout.addLayout(btn_row)

    def connect_engine(self, engine: NANDEngine):
        self.engine = engine
        engine.operation_started.connect(self._on_op_started)
        engine.operation_progress.connect(self._on_op_progress)
        engine.operation_completed.connect(self._on_op_completed)
        engine.bad_block_found.connect(self._on_bad_block)
        engine.connection_changed.connect(self._on_connection_changed)
        engine.device_detected.connect(self._on_device_detected)

    def _start_scan(self):
        if not self.engine or not self.engine.serial.connected:
            self.lbl_status.setText("⚠ Not connected")
            return
        self.table.setRowCount(0)
        self.engine.scan_bad_blocks()

    def _on_device_detected(self, dev):
        self.val_total.setText(str(dev.total_blocks))

    @pyqtSlot(int)
    def _on_bad_block(self, block: int):
        if not self.engine:
            return
        row = self.table.rowCount()
        self.table.insertRow(row)

        dev = self.engine.device_info
        page = block * dev.pages_per_block

        items = [
            QTableWidgetItem(str(block)),
            QTableWidgetItem(f"0x{page:06X}"),
            QTableWidgetItem("Factory Bad"),
        ]
        for col, item in enumerate(items):
            item.setForeground(QColor(COLORS["accent_red2"]))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, col, item)

        # Update stats
        bad = row + 1
        self.val_bad.setText(str(bad))
        total = self.engine.device_info.total_blocks
        if total > 0:
            self.val_percent.setText(f"{bad/total*100:.2f}%")
        self.val_good.setText(str(max(0, total - bad)))

    @pyqtSlot(OperationProgress)
    def _on_op_started(self, op: OperationProgress):
        if op.op_type == OperationType.SCAN_BAD_BLOCKS:
            self.btn_scan.setEnabled(False)
            self.btn_cancel.setEnabled(True)
            self.lbl_status.setText("Scanning…")
            self.lbl_status.setStyleSheet(f"color: {COLORS['accent_blue']};")

    @pyqtSlot(OperationProgress)
    def _on_op_progress(self, op: OperationProgress):
        if op.op_type == OperationType.SCAN_BAD_BLOCKS:
            self.lbl_status.setText(
                f"Block {op.current}/{op.total}  ({op.percent:.1f}%)  "
                f"{len(op.bad_blocks)} bad found"
            )

    @pyqtSlot(OperationProgress)
    def _on_op_completed(self, op: OperationProgress):
        if op.op_type == OperationType.SCAN_BAD_BLOCKS:
            self.btn_scan.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            if op.status == OperationStatus.COMPLETED:
                self.lbl_status.setText(
                    f"✓ Scan complete  {len(op.bad_blocks)} bad blocks found"
                )
                self.lbl_status.setStyleSheet(f"color: {COLORS['accent_green2']};")
            else:
                self.lbl_status.setText(f"✗ {op.status.value}")
                self.lbl_status.setStyleSheet(f"color: {COLORS['accent_red2']};")

    @pyqtSlot(bool, str)
    def _on_connection_changed(self, connected: bool, _: str):
        self.btn_scan.setEnabled(connected)
