"""Erase Panel - Full chip erase operations."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QCheckBox, QFrame, QMessageBox, QSpinBox
)
from PyQt6.QtCore import pyqtSlot

from ...core.nand_engine import NANDEngine
from ...models.nand_models import OperationProgress, OperationStatus, OperationType
from ..theme import COLORS


class ErasePanel(QWidget):
    def __init__(self, engine: NANDEngine = None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("🗑  Erase NAND Flash")
        title.setStyleSheet(
            f"color: {COLORS['accent_red2']}; font-size: 14pt; font-weight: 700;"
        )
        layout.addWidget(title)

        desc = QLabel(
            "Erase all user blocks on the NAND Flash chip. "
            "Factory-marked bad blocks are preserved by default."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLORS['fg_muted']}; font-size: 9pt;")
        layout.addWidget(desc)

        # Warning banner
        warn = QFrame()
        warn.setStyleSheet(
            f"background-color: #2D0B0B; border: 1px solid {COLORS['accent_red']}; "
            f"border-radius: 5px;"
        )
        wl = QHBoxLayout(warn)
        wl.setContentsMargins(10, 8, 10, 8)
        wl.addWidget(QLabel("⚠", styleSheet=f"color: {COLORS['accent_red2']}; font-size: 16pt; font-weight: bold;"))
        wt = QLabel(
            "ERASE OPERATION — All data will be PERMANENTLY DELETED.\n"
            "This cannot be undone. Ensure you have a backup."
        )
        wt.setStyleSheet(f"color: {COLORS['accent_red2']}; font-size: 9pt;")
        wt.setWordWrap(True)
        wl.addWidget(wt, stretch=1)
        layout.addWidget(warn)

        # Options
        opt_grp = QGroupBox("Erase Options")
        opt_form = QFormLayout(opt_grp)
        opt_form.setSpacing(8)
        opt_form.setContentsMargins(12, 14, 12, 10)

        self.chk_skip_bad = QCheckBox("Skip bad blocks (recommended)")
        self.chk_skip_bad.setChecked(True)
        opt_form.addRow("Bad Blocks:", self.chk_skip_bad)

        self.chk_verify = QCheckBox("Verify erase (check each block is 0xFF)")
        self.chk_verify.setChecked(False)
        opt_form.addRow("Verify:", self.chk_verify)

        self.chk_wp_off = QCheckBox("Disable write protect before erasing")
        self.chk_wp_off.setChecked(True)
        opt_form.addRow("Write Protect:", self.chk_wp_off)
        layout.addWidget(opt_grp)

        # Range
        range_grp = QGroupBox("Block Range (leave at 0 for full chip)")
        range_form = QFormLayout(range_grp)
        range_form.setSpacing(8)
        range_form.setContentsMargins(12, 14, 12, 10)

        self.spin_start = QSpinBox()
        self.spin_start.setMinimum(0)
        self.spin_start.setMaximum(100000)
        self.spin_start.setValue(0)
        range_form.addRow("Start Block:", self.spin_start)

        self.spin_end = QSpinBox()
        self.spin_end.setMinimum(0)
        self.spin_end.setMaximum(100000)
        self.spin_end.setValue(0)
        self.spin_end.setSpecialValueText("End of chip")
        range_form.addRow("End Block:", self.spin_end)
        layout.addWidget(range_grp)

        layout.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(sep)

        btn_row = QHBoxLayout()
        self.btn_erase = QPushButton("🗑  Erase Chip")
        self.btn_erase.setObjectName("btn_danger")
        self.btn_erase.setMinimumWidth(140)
        self.btn_erase.setMinimumHeight(36)
        self.btn_erase.clicked.connect(self._start_erase)
        btn_row.addWidget(self.btn_erase)

        self.btn_cancel = QPushButton("⬛  Cancel")
        self.btn_cancel.setObjectName("btn_warning")
        self.btn_cancel.setMinimumWidth(100)
        self.btn_cancel.setMinimumHeight(36)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(lambda: self.engine and self.engine.cancel_operation())
        btn_row.addWidget(self.btn_cancel)

        btn_row.addStretch()

        self.lbl_status = QLabel("Idle")
        self.lbl_status.setStyleSheet(f"color: {COLORS['fg_muted']}; font-size: 9pt;")
        btn_row.addWidget(self.lbl_status)
        layout.addLayout(btn_row)

    def connect_engine(self, engine: NANDEngine):
        self.engine = engine
        engine.operation_started.connect(self._on_op_started)
        engine.operation_progress.connect(self._on_op_progress)
        engine.operation_completed.connect(self._on_op_completed)
        engine.connection_changed.connect(self._on_connection_changed)

    def _start_erase(self):
        if not self.engine or not self.engine.serial.connected:
            self.lbl_status.setText("⚠ Not connected")
            return
        ret = QMessageBox.warning(
            self, "Confirm Chip Erase",
            "⚠ ALL DATA ON THE CHIP WILL BE PERMANENTLY DELETED!\n\n"
            "This operation cannot be undone.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        if self.chk_wp_off.isChecked():
            self.engine.serial.set_write_protect(False)
        self.engine.session.skip_bad_blocks = self.chk_skip_bad.isChecked()
        self.engine.erase_chip()

    @pyqtSlot(OperationProgress)
    def _on_op_started(self, op: OperationProgress):
        if op.op_type == OperationType.ERASE_ALL:
            self.btn_erase.setEnabled(False)
            self.btn_cancel.setEnabled(True)
            self.lbl_status.setText("Erasing…")
            self.lbl_status.setStyleSheet(f"color: {COLORS['accent_red2']};")

    @pyqtSlot(OperationProgress)
    def _on_op_progress(self, op: OperationProgress):
        if op.op_type == OperationType.ERASE_ALL:
            self.lbl_status.setText(
                f"Erasing block {op.current}/{op.total}  ({op.percent:.1f}%)"
            )

    @pyqtSlot(OperationProgress)
    def _on_op_completed(self, op: OperationProgress):
        if op.op_type == OperationType.ERASE_ALL:
            self.btn_erase.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            if op.status == OperationStatus.COMPLETED:
                self.lbl_status.setText(f"✓ Erase complete  {len(op.errors)} block errors")
                self.lbl_status.setStyleSheet(f"color: {COLORS['accent_green2']};")
            else:
                self.lbl_status.setText(f"✗ {op.status.value}")
                self.lbl_status.setStyleSheet(f"color: {COLORS['accent_red2']};")

    @pyqtSlot(bool, str)
    def _on_connection_changed(self, connected: bool, _: str):
        self.btn_erase.setEnabled(connected)
