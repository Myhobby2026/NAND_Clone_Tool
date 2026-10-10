"""Clone Panel - Clone NAND chip to chip."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QCheckBox, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSlot

from ...core.nand_engine import NANDEngine
from ...models.nand_models import OperationProgress, OperationStatus, OperationType
from ..theme import COLORS


class ClonePanel(QWidget):
    def __init__(self, engine: NANDEngine = None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("⧉  Clone NAND Flash")
        title.setStyleSheet(
            f"color: #CBA6F7; font-size: 14pt; font-weight: 700;"
        )
        layout.addWidget(title)

        desc = QLabel(
            "Clone NAND Flash chip-to-chip. Phase 1 reads the source chip "
            "into memory, then Phase 2 programs the destination chip. "
            "The tool will prompt you to swap chips between phases."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLORS['fg_muted']}; font-size: 9pt;")
        layout.addWidget(desc)

        # Process flow diagram
        flow = QFrame()
        flow.setStyleSheet(
            f"background-color: {COLORS['bg_secondary']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 6px;"
        )
        flow_layout = QHBoxLayout(flow)
        flow_layout.setContentsMargins(16, 12, 16, 12)
        flow_layout.setSpacing(8)

        def step_label(icon, text, color):
            w = QWidget()
            vl = QVBoxLayout(w)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(2)
            l1 = QLabel(icon)
            l1.setStyleSheet(f"color: {color}; font-size: 18pt;")
            l1.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l2 = QLabel(text)
            l2.setStyleSheet(f"color: {color}; font-size: 8pt; font-weight: 600;")
            l2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vl.addWidget(l1)
            vl.addWidget(l2)
            return w

        flow_layout.addWidget(step_label("📦", "Source Chip", COLORS["accent_blue"]))
        flow_layout.addWidget(QLabel("→", styleSheet=f"color: {COLORS['fg_muted']}; font-size: 16pt;"))
        flow_layout.addWidget(step_label("📥", "Phase 1\nRead", COLORS["accent_blue"]))
        flow_layout.addWidget(QLabel("→", styleSheet=f"color: {COLORS['fg_muted']}; font-size: 16pt;"))
        flow_layout.addWidget(step_label("💾", "Memory\nBuffer", COLORS["accent_orange2"]))
        flow_layout.addWidget(QLabel("→", styleSheet=f"color: {COLORS['fg_muted']}; font-size: 16pt;"))
        flow_layout.addWidget(step_label("📤", "Phase 2\nWrite", COLORS["accent_green2"]))
        flow_layout.addWidget(QLabel("→", styleSheet=f"color: {COLORS['fg_muted']}; font-size: 16pt;"))
        flow_layout.addWidget(step_label("📦", "Dest. Chip", COLORS["accent_green2"]))
        layout.addWidget(flow)

        # Options
        opt_grp = QGroupBox("Clone Options")
        opt_form = QFormLayout(opt_grp)
        opt_form.setSpacing(8)
        opt_form.setContentsMargins(12, 14, 12, 10)

        self.chk_ecc = QCheckBox("Apply ECC correction during read")
        self.chk_ecc.setChecked(True)
        opt_form.addRow("ECC:", self.chk_ecc)

        self.chk_skip_bad = QCheckBox("Skip bad blocks on source")
        self.chk_skip_bad.setChecked(True)
        opt_form.addRow("Bad Blocks:", self.chk_skip_bad)

        self.chk_verify = QCheckBox("Verify destination after write")
        self.chk_verify.setChecked(True)
        opt_form.addRow("Verify:", self.chk_verify)
        layout.addWidget(opt_grp)

        # Phase indicator
        phase_grp = QGroupBox("Progress")
        phase_layout = QVBoxLayout(phase_grp)
        phase_layout.setContentsMargins(12, 14, 12, 10)

        self.lbl_phase = QLabel("Phase: Waiting")
        self.lbl_phase.setStyleSheet(
            f"color: {COLORS['accent_blue']}; font-size: 10pt; font-weight: 600;"
        )
        phase_layout.addWidget(self.lbl_phase)
        layout.addWidget(phase_grp)

        layout.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(sep)

        btn_row = QHBoxLayout()
        self.btn_clone = QPushButton("⧉  Start Clone")
        self.btn_clone.setObjectName("btn_primary")
        self.btn_clone.setMinimumWidth(140)
        self.btn_clone.setMinimumHeight(36)
        self.btn_clone.clicked.connect(self._start_clone)
        btn_row.addWidget(self.btn_clone)

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

    def _start_clone(self):
        if not self.engine or not self.engine.serial.connected:
            self.lbl_status.setText("⚠ Not connected")
            return
        ret = QMessageBox.question(
            self, "Start Clone Operation",
            "Clone will:\n1. Read source chip into memory\n2. Prompt to swap chips\n3. Program destination chip\n\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        self.engine.session.use_ecc = self.chk_ecc.isChecked()
        self.engine.session.skip_bad_blocks = self.chk_skip_bad.isChecked()
        self.engine.session.verify_after_write = self.chk_verify.isChecked()
        self.engine.clone_chip()

    @pyqtSlot(OperationProgress)
    def _on_op_started(self, op: OperationProgress):
        if op.op_type == OperationType.CLONE:
            self.btn_clone.setEnabled(False)
            self.btn_cancel.setEnabled(True)
            self.lbl_phase.setText("Phase 1: Reading source…")
            self.lbl_status.setText("Cloning…")

    @pyqtSlot(OperationProgress)
    def _on_op_progress(self, op: OperationProgress):
        if op.op_type == OperationType.CLONE:
            half = op.total // 2
            if op.current <= half:
                self.lbl_phase.setText(f"Phase 1: Reading  {op.percent:.1f}%")
            else:
                self.lbl_phase.setText(f"Phase 2: Writing  {op.percent:.1f}%")
            self.lbl_status.setText(
                f"{op.throughput_kbps:.0f} KB/s  {op.bytes_processed // 1024} KB"
            )

    @pyqtSlot(OperationProgress)
    def _on_op_completed(self, op: OperationProgress):
        if op.op_type == OperationType.CLONE:
            self.btn_clone.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            if op.status == OperationStatus.COMPLETED:
                self.lbl_phase.setText("Phase: Complete ✓")
                self.lbl_status.setText(f"✓ Clone complete  {len(op.errors)} errors")
                self.lbl_status.setStyleSheet(f"color: {COLORS['accent_green2']};")
            else:
                self.lbl_phase.setText("Phase: Failed")
                self.lbl_status.setText(f"✗ {op.status.value}")
                self.lbl_status.setStyleSheet(f"color: {COLORS['accent_red2']};")

    @pyqtSlot(bool, str)
    def _on_connection_changed(self, connected: bool, _: str):
        self.btn_clone.setEnabled(connected)
