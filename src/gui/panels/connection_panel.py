"""Connection Panel - Port selection and Teensy connection management."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QFormLayout, QFrame
)
from PyQt6.QtCore import Qt, pyqtSlot

from ...core.nand_engine import NANDEngine
from ..theme import COLORS


class PortSelector(QComboBox):
    """Serial port selection combo with auto-refresh."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.refresh()

    def refresh(self):
        from ...core.serial_manager import SerialManager
        current = self.currentText()
        self.clear()
        ports = SerialManager.list_ports()
        for p in ports:
            desc = p["description"] or p["port"]
            tag  = " ★" if p["is_teensy"] else ""
            self.addItem(f'{p["port"]} – {desc[:30]}{tag}', userData=p["port"])
        # Re-select previous
        idx = self.findData(current)
        if idx >= 0:
            self.setCurrentIndex(idx)

    def current_port(self) -> str:
        idx = self.currentIndex()
        if idx >= 0:
            return self.itemData(idx) or self.currentText().split(" – ")[0]
        return self.currentText().split(" – ")[0]


class ConnectionPanel(QWidget):
    """Full connection management panel (used in connect dialog)."""

    def __init__(self, engine: NANDEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        grp = QGroupBox("Serial Connection")
        grp_layout = QFormLayout(grp)
        grp_layout.setSpacing(8)

        # Port
        port_row = QHBoxLayout()
        self.port_combo = PortSelector()
        self.btn_refresh = QPushButton("↻")
        self.btn_refresh.setFixedWidth(36)
        self.btn_refresh.setToolTip("Refresh port list")
        self.btn_refresh.clicked.connect(self.port_combo.refresh)
        port_row.addWidget(self.port_combo)
        port_row.addWidget(self.btn_refresh)
        grp_layout.addRow("Port:", port_row)

        # Baud
        self.lbl_baud = QLabel("2,000,000 baud")
        self.lbl_baud.setStyleSheet(f"color: {COLORS['fg_muted']};")
        grp_layout.addRow("Baud Rate:", self.lbl_baud)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.setObjectName("btn_primary")
        self.btn_connect.clicked.connect(self._connect)

        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setObjectName("btn_danger")
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.clicked.connect(self._disconnect)

        btn_row.addWidget(self.btn_connect)
        btn_row.addWidget(self.btn_disconnect)
        grp_layout.addRow("", btn_row)

        layout.addWidget(grp)

    def connect_engine(self, engine: NANDEngine):
        engine.connection_changed.connect(self._on_connection_changed)

    def _connect(self):
        port = self.port_combo.current_port()
        if port:
            self.engine.connect(port)

    def _disconnect(self):
        self.engine.disconnect()

    @pyqtSlot(bool, str)
    def _on_connection_changed(self, connected: bool, msg: str):
        self.btn_connect.setEnabled(not connected)
        self.btn_disconnect.setEnabled(connected)
