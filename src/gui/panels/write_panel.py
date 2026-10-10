"""Write Panel - Program a NAND Flash chip from a dump file."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QCheckBox, QFileDialog,
    QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSlot

from ...core.nand_engine import NANDEngine
from ...models.nand_models import OperationProgress, OperationStatus, OperationType
from ..theme import COLORS


class WritePanel(QWidget):
    """Panel for writing a dump file to NAND Flash."""

    def __init__(self, engine: NANDEngine = None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("📤  Write / Program NAND Flash")
        title.setStyleSheet(
            f"color: {COLORS['accent_green2']}; font-size: 14pt; font-weight: 700;"
        )
        layout.addWidget(title)

        desc = QLabel(
            "Program a binary dump file into the NAND Flash chip. "
            "Each block is automatically erased before writing. "
            "⚠ This operation will destroy existing chip contents."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLORS['fg_muted']}; font-size: 9pt;")
        layout.addWidget(desc)

        # ── Warning Banner ─────────────────────────────────────
        warn_frame = QFrame()
        warn_frame.setStyleSheet(
            f"background-color: #3D1A00; border: 1px solid {COLORS['accent_orange']}; "
            f"border-radius: 5px; padding: 6px;"
        )
        warn_layout = QHBoxLayout(warn_frame)
        warn_layout.setContentsMargins(10, 6, 10, 6)
        warn_icon = QLabel("⚠")
        warn_icon.setStyleSheet(
            f"color: {COLORS['accent_orange2']}; font-size: 16pt; font-weight: bold;"
        )
        warn_layout.addWidget(warn_icon)
        warn_text = QLabel(
            "WRITE OPERATION — This will PERMANENTLY OVERWRITE chip contents.\n"
            "Make sure you have a backup and the correct file is selected."
        )
        warn_text.setStyleSheet(f"color: {COLORS['accent_orange2']}; font-size: 9pt;")
        warn_text.setWordWrap(True)
        warn_layout.addWidget(warn_text, stretch=1)
        layout.addWidget(warn_frame)

        # ── Source File ───────────────────────────────────────
        file_grp = QGroupBox("Source File")
        file_layout = QVBoxLayout(file_grp)
        file_layout.setSpacing(8)

        src_row = QHBoxLayout()
        self.edit_source = QLineEdit()
        self.edit_source.setPlaceholderText("Select NAND dump file to program…")
        src_row.addWidget(self.edit_source)

        self.btn_browse = QPushButton("Browse…")
        self.btn_browse.setFixedWidth(90)
        self.btn_browse.clicked.connect(self._browse_source)
        src_row.addWidget(self.btn_browse)
        file_layout.addLayout(src_row)

        # File info row
        self.lbl_file_info = QLabel("No file selected")
        self.lbl_file_info.setStyleSheet(f"color: {COLORS['fg_muted']}; font-size: 9pt;")
        file_layout.addWidget(self.lbl_file_info)
        layout.addWidget(file_grp)

        # ── Options ───────────────────────────────────────────
        opt_grp = QGroupBox("Write Options")
        opt_form = QFormLayout(opt_grp)
        opt_form.setSpacing(8)
        opt_form.setContentsMargins(12, 14, 12, 10)

        self.chk_skip_bad = QCheckBox("Skip bad blocks")
        self.chk_skip_bad.setChecked(True)
        opt_form.addRow("Bad Blocks:", self.chk_skip_bad)

        self.chk_erase_first = QCheckBox("Erase block before writing (recommended)")
        self.chk_erase_first.setChecked(True)
        opt_form.addRow("Erase:", self.chk_erase_first)

        self.chk_verify = QCheckBox("Verify after write (slower but reliable)")
        self.chk_verify.setChecked(True)
        opt_form.addRow("Verify:", self.chk_verify)

        self.chk_wp_off = QCheckBox("Disable write protect before writing")
        self.chk_wp_off.setChecked(True)
        opt_form.addRow("Write Protect:", self.chk_wp_off)
        layout.addWidget(opt_grp)

        layout.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_write = QPushButton("▶  Start Write")
        self.btn_write.setObjectName("btn_success")
        self.btn_write.setMinimumWidth(140)
        self.btn_write.setMinimumHeight(36)
        self.btn_write.clicked.connect(self._start_write)
        btn_row.addWidget(self.btn_write)

        self.btn_cancel = QPushButton("⬛  Cancel")
        self.btn_cancel.setObjectName("btn_danger")
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

    def set_source_file(self, path: str):
        self.edit_source.setText(path)
        self._update_file_info(path)

    def _browse_source(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open NAND Dump File", "",
            "NAND Dump Files (*.bin *.img *.nandimg *.raw);;All Files (*)"
        )
        if path:
            self.edit_source.setText(path)
            self._update_file_info(path)

    def _update_file_info(self, path: str):
        import os
        if os.path.isfile(path):
            size = os.path.getsize(path)
            mb = size / (1024 * 1024)
            self.lbl_file_info.setText(
                f"File size: {mb:.2f} MB  ({size:,} bytes)"
            )
            self.lbl_file_info.setStyleSheet(
                f"color: {COLORS['accent_green2']}; font-size: 9pt;"
            )
        else:
            self.lbl_file_info.setText("File not found")
            self.lbl_file_info.setStyleSheet(
                f"color: {COLORS['accent_red2']}; font-size: 9pt;"
            )

    def _start_write(self):
        src = self.edit_source.text().strip()
        if not src:
            self.lbl_status.setText("⚠ Select source file first")
            return
        if not self.engine or not self.engine.serial.connected:
            self.lbl_status.setText("⚠ Not connected")
            return

        ret = QMessageBox.warning(
            self, "Confirm Write Operation",
            "⚠ This will PERMANENTLY OVERWRITE the chip contents!\n\n"
            f"Source: {src}\n\n"
            "Are you absolutely sure you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if ret != QMessageBox.StandardButton.Yes:
            return

        self.engine.session.source_file  = src
        self.engine.session.skip_bad_blocks = self.chk_skip_bad.isChecked()
        self.engine.session.verify_after_write = self.chk_verify.isChecked()

        if self.chk_wp_off.isChecked():
            self.engine.serial.set_write_protect(False)

        self.engine.write_chip(src)

    @pyqtSlot(OperationProgress)
    def _on_op_started(self, op: OperationProgress):
        if op.op_type == OperationType.WRITE_FULL_DUMP:
            self.btn_write.setEnabled(False)
            self.btn_cancel.setEnabled(True)
            self.lbl_status.setText("Writing…")
            self.lbl_status.setStyleSheet(f"color: {COLORS['accent_green2']};")

    @pyqtSlot(OperationProgress)
    def _on_op_progress(self, op: OperationProgress):
        if op.op_type == OperationType.WRITE_FULL_DUMP:
            mb = op.bytes_processed / (1024 * 1024)
            self.lbl_status.setText(
                f"{op.percent:.1f}%  {mb:.2f} MB  {op.throughput_kbps:.0f} KB/s"
            )

    @pyqtSlot(OperationProgress)
    def _on_op_completed(self, op: OperationProgress):
        if op.op_type == OperationType.WRITE_FULL_DUMP:
            self.btn_write.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            if op.status == OperationStatus.COMPLETED:
                self.lbl_status.setText(f"✓ Complete  {len(op.errors)} errors")
                self.lbl_status.setStyleSheet(f"color: {COLORS['accent_green2']};")
            else:
                self.lbl_status.setText(f"✗ {op.status.value}")
                self.lbl_status.setStyleSheet(f"color: {COLORS['accent_red2']};")

    @pyqtSlot(bool, str)
    def _on_connection_changed(self, connected: bool, _: str):
        self.btn_write.setEnabled(connected)
