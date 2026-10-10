"""Read Panel - Full chip read/dump operations."""

from __future__ import annotations
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QCheckBox,
    QFileDialog, QProgressBar, QFrame, QComboBox, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSlot

from ...core.nand_engine import NANDEngine
from ...models.nand_models import OperationProgress, OperationStatus, OperationType
from ..theme import COLORS


class ReadPanel(QWidget):
    """Panel for reading full NAND Flash chip dump."""

    def __init__(self, engine: NANDEngine = None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Title ──────────────────────────────────────────────
        title = QLabel("📥  Read NAND Flash")
        title.setStyleSheet(
            f"color: {COLORS['accent_blue']}; font-size: 14pt; font-weight: 700;"
        )
        layout.addWidget(title)

        desc = QLabel(
            "Read the entire NAND Flash chip and save to a binary dump file. "
            "ECC correction is applied automatically during reading."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLORS['fg_muted']}; font-size: 9pt;")
        layout.addWidget(desc)

        # ── Output File ───────────────────────────────────────
        file_grp = QGroupBox("Output File")
        file_layout = QVBoxLayout(file_grp)
        file_layout.setSpacing(8)

        out_row = QHBoxLayout()
        self.edit_output = QLineEdit()
        self.edit_output.setPlaceholderText("Select output file path…")
        self.edit_output.setReadOnly(False)
        out_row.addWidget(self.edit_output)

        self.btn_browse = QPushButton("Browse…")
        self.btn_browse.setFixedWidth(90)
        self.btn_browse.clicked.connect(self._browse_output)
        out_row.addWidget(self.btn_browse)
        file_layout.addLayout(out_row)

        # Format selector
        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.combo_format = QComboBox()
        self.combo_format.addItems([
            "Raw Binary (.bin)",
            "NAND Image (.nandimg)",
            "Raw Image (.img)",
        ])
        self.combo_format.setMaximumWidth(220)
        fmt_row.addWidget(self.combo_format)
        fmt_row.addStretch()
        file_layout.addLayout(fmt_row)
        layout.addWidget(file_grp)

        # ── Options ───────────────────────────────────────────
        opt_grp = QGroupBox("Read Options")
        opt_form = QFormLayout(opt_grp)
        opt_form.setSpacing(8)
        opt_form.setContentsMargins(12, 14, 12, 10)

        self.chk_ecc = QCheckBox("Apply ECC correction")
        self.chk_ecc.setChecked(True)
        opt_form.addRow("ECC:", self.chk_ecc)

        self.chk_skip_bad = QCheckBox("Skip bad blocks (fill with 0xFF)")
        self.chk_skip_bad.setChecked(True)
        opt_form.addRow("Bad Blocks:", self.chk_skip_bad)

        self.chk_oob = QCheckBox("Include OOB (spare) data")
        self.chk_oob.setChecked(False)
        opt_form.addRow("OOB:", self.chk_oob)

        self.chk_verify = QCheckBox("Verify by re-reading after dump")
        self.chk_verify.setChecked(False)
        opt_form.addRow("Verify:", self.chk_verify)
        layout.addWidget(opt_grp)

        # ── Range (optional) ─────────────────────────────────
        range_grp = QGroupBox("Page Range (optional)")
        range_form = QFormLayout(range_grp)
        range_form.setSpacing(8)
        range_form.setContentsMargins(12, 14, 12, 10)

        self.chk_range = QCheckBox("Limit to page range")
        self.chk_range.setChecked(False)
        self.chk_range.stateChanged.connect(self._toggle_range)
        range_form.addRow("", self.chk_range)

        self.spin_start = QSpinBox()
        self.spin_start.setMinimum(0)
        self.spin_start.setMaximum(10_000_000)
        self.spin_start.setValue(0)
        self.spin_start.setEnabled(False)
        range_form.addRow("Start Page:", self.spin_start)

        self.spin_end = QSpinBox()
        self.spin_end.setMinimum(1)
        self.spin_end.setMaximum(10_000_000)
        self.spin_end.setValue(65535)
        self.spin_end.setEnabled(False)
        range_form.addRow("End Page:", self.spin_end)
        layout.addWidget(range_grp)

        layout.addStretch()

        # ── Buttons ───────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_read = QPushButton("▶  Start Read")
        self.btn_read.setObjectName("btn_primary")
        self.btn_read.setMinimumWidth(140)
        self.btn_read.setMinimumHeight(36)
        self.btn_read.clicked.connect(self._start_read)
        btn_row.addWidget(self.btn_read)

        self.btn_cancel = QPushButton("⬛  Cancel")
        self.btn_cancel.setObjectName("btn_danger")
        self.btn_cancel.setMinimumWidth(100)
        self.btn_cancel.setMinimumHeight(36)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
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

    def set_output_file(self, path: str):
        self.edit_output.setText(path)

    def _browse_output(self):
        fmt = self.combo_format.currentIndex()
        filters = [
            "Binary Dump (*.bin)",
            "NAND Image (*.nandimg)",
            "Raw Image (*.img)",
        ]
        path, _ = QFileDialog.getSaveFileName(
            self, "Save NAND Dump", "", f"{filters[fmt]};;All Files (*)"
        )
        if path:
            self.edit_output.setText(path)

    def _toggle_range(self, state: int):
        enabled = bool(state)
        self.spin_start.setEnabled(enabled)
        self.spin_end.setEnabled(enabled)

    def _start_read(self):
        out_path = self.edit_output.text().strip()
        if not out_path:
            self.lbl_status.setText("⚠ Select output file first")
            self.lbl_status.setStyleSheet(f"color: {COLORS['accent_orange2']};")
            return
        if not self.engine or not self.engine.serial.connected:
            self.lbl_status.setText("⚠ Not connected")
            self.lbl_status.setStyleSheet(f"color: {COLORS['accent_red2']};")
            return

        # Apply options to session
        self.engine.session.use_ecc         = self.chk_ecc.isChecked()
        self.engine.session.skip_bad_blocks = self.chk_skip_bad.isChecked()
        self.engine.session.include_oob     = self.chk_oob.isChecked()
        self.engine.session.output_file     = out_path
        self.engine.session.verify_after_write = self.chk_verify.isChecked()

        self.engine.read_chip(out_path)

    def _cancel(self):
        if self.engine:
            self.engine.cancel_operation()

    @pyqtSlot(OperationProgress)
    def _on_op_started(self, op: OperationProgress):
        if op.op_type == OperationType.READ_FULL_DUMP:
            self.btn_read.setEnabled(False)
            self.btn_cancel.setEnabled(True)
            self.lbl_status.setText("Reading…")
            self.lbl_status.setStyleSheet(f"color: {COLORS['accent_blue']};")

    @pyqtSlot(OperationProgress)
    def _on_op_progress(self, op: OperationProgress):
        if op.op_type == OperationType.READ_FULL_DUMP:
            mb = op.bytes_processed / (1024 * 1024)
            self.lbl_status.setText(
                f"{op.percent:.1f}%  {mb:.2f} MB  {op.throughput_kbps:.0f} KB/s"
            )

    @pyqtSlot(OperationProgress)
    def _on_op_completed(self, op: OperationProgress):
        if op.op_type == OperationType.READ_FULL_DUMP:
            self.btn_read.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            if op.status == OperationStatus.COMPLETED:
                mb = op.bytes_processed / (1024 * 1024)
                self.lbl_status.setText(
                    f"✓ Done  {mb:.2f} MB  "
                    f"{op.ecc_corrected} corrections  "
                    f"{op.ecc_errors} uncorrectable"
                )
                self.lbl_status.setStyleSheet(f"color: {COLORS['accent_green2']};")
            else:
                self.lbl_status.setText(f"✗ {op.status.value}")
                self.lbl_status.setStyleSheet(f"color: {COLORS['accent_red2']};")

    @pyqtSlot(bool, str)
    def _on_connection_changed(self, connected: bool, _: str):
        self.btn_read.setEnabled(connected)
