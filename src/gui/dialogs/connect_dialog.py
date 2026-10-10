"""Connect Dialog - Serial port connection dialog."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFormLayout, QGroupBox, QDialogButtonBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSlot

from ...core.nand_engine import NANDEngine
from ...core.serial_manager import SerialManager
from ..theme import COLORS
from ..panels.connection_panel import PortSelector


class ConnectDialog(QDialog):
    def __init__(self, engine: NANDEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.setWindowTitle("Connect to Teensy 4.1")
        self.setMinimumWidth(420)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("🔌  Connect to Teensy 4.1")
        title.setStyleSheet(
            f"color: {COLORS['accent_blue']}; font-size: 12pt; font-weight: 700;"
        )
        layout.addWidget(title)

        # Port selection
        form_grp = QGroupBox("Serial Port")
        form = QFormLayout(form_grp)
        form.setSpacing(10)

        port_row = QHBoxLayout()
        self.port_combo = PortSelector()
        self.btn_refresh = QPushButton("↻")
        self.btn_refresh.setFixedWidth(36)
        self.btn_refresh.clicked.connect(self.port_combo.refresh)
        port_row.addWidget(self.port_combo)
        port_row.addWidget(self.btn_refresh)
        form.addRow("Port:", port_row)

        baud_lbl = QLabel("2,000,000 baud  (fixed)")
        baud_lbl.setStyleSheet(f"color: {COLORS['fg_muted']};")
        form.addRow("Baud Rate:", baud_lbl)

        layout.addWidget(form_grp)

        # Detected Teensy ports
        teensy_ports = [p for p in SerialManager.list_ports() if p["is_teensy"]]
        if teensy_ports:
            hint = QFrame()
            hint.setStyleSheet(
                f"background-color: #0A2A10; border: 1px solid {COLORS['accent_green']};"
                f"border-radius: 4px; padding: 6px;"
            )
            hl = QVBoxLayout(hint)
            hl.setContentsMargins(8, 6, 8, 6)
            hl.addWidget(QLabel(
                f"✓  Teensy detected: {', '.join(p['port'] for p in teensy_ports)}",
                styleSheet=f"color: {COLORS['accent_green2']}; font-size: 9pt;"
            ))
            layout.addWidget(hint)

        # Status
        self.lbl_status = QLabel("Click Connect to establish connection.")
        self.lbl_status.setStyleSheet(f"color: {COLORS['fg_muted']}; font-size: 9pt;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setObjectName("btn_primary")
        self.btn_connect.setMinimumWidth(100)
        self.btn_connect.clicked.connect(self._do_connect)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)

        btn_row.addStretch()
        btn_row.addWidget(self.btn_connect)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        self.engine.connection_changed.connect(self._on_connection_changed)

    def _do_connect(self):
        port = self.port_combo.current_port()
        if not port:
            self.lbl_status.setText("⚠ Please select a port.")
            return
        self.lbl_status.setText(f"Connecting to {port}…")
        self.btn_connect.setEnabled(False)
        self.engine.connect(port)

    @pyqtSlot(bool, str)
    def _on_connection_changed(self, connected: bool, msg: str):
        if connected:
            self.lbl_status.setText(f"✓  {msg}")
            self.lbl_status.setStyleSheet(f"color: {COLORS['accent_green2']};")
            self.accept()
        else:
            self.lbl_status.setText(f"✗  {msg}")
            self.lbl_status.setStyleSheet(f"color: {COLORS['accent_red2']};")
            self.btn_connect.setEnabled(True)
