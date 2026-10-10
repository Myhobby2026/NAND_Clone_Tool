"""Hardware Wiring Guide Dialog."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QFrame, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from ..theme import COLORS


WIRING_TABLE = [
    # (Teensy Pin, Signal, NAND Pin, Description)
    ("0",  "I/O 0",  "DQ0",  "Data Bit 0"),
    ("1",  "I/O 1",  "DQ1",  "Data Bit 1"),
    ("2",  "I/O 2",  "DQ2",  "Data Bit 2"),
    ("3",  "I/O 3",  "DQ3",  "Data Bit 3"),
    ("4",  "I/O 4",  "DQ4",  "Data Bit 4"),
    ("5",  "I/O 5",  "DQ5",  "Data Bit 5"),
    ("6",  "I/O 6",  "DQ6",  "Data Bit 6"),
    ("7",  "I/O 7",  "DQ7",  "Data Bit 7"),
    ("8",  "CLE",   "CLE",  "Command Latch Enable"),
    ("9",  "ALE",   "ALE",  "Address Latch Enable"),
    ("10", "WE#",   "WE",   "Write Enable (active low)"),
    ("11", "RE#",   "RE",   "Read Enable (active low)"),
    ("12", "CE#",   "CE",   "Chip Enable (active low)"),
    ("13", "R/B#",  "R/B",  "Ready/Busy (input, pullup)"),
    ("14", "WP#",   "WP",   "Write Protect (active low)"),
    ("15", "VCC_EN","—",    "3.3V power via P-MOSFET gate"),
    ("3.3V","VCC",  "VCC",  "3.3V supply (from MOSFET drain)"),
    ("GND", "GND",  "VSS",  "Ground"),
]


class WiringDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hardware Wiring Guide")
        self.setMinimumSize(640, 560)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        title = QLabel("🔌  Hardware Wiring Guide")
        title.setStyleSheet(
            f"color: {COLORS['accent_blue']}; font-size: 13pt; font-weight: 700;"
        )
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_wiring_tab(), "Pin Mapping")
        tabs.addTab(self._build_notes_tab(), "Notes & Precautions")
        layout.addWidget(tabs, stretch=1)

        btn = QPushButton("Close")
        btn.setFixedWidth(80)
        btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn)
        layout.addLayout(row)

    def _build_wiring_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)

        info = QLabel(
            "Wire the Teensy 4.1 to the NAND Flash chip as follows.\n"
            "All signals are 3.3V logic. Do NOT connect 5V to NAND pins."
        )
        info.setStyleSheet(f"color: {COLORS['fg_muted']}; font-size: 9pt;")
        info.setWordWrap(True)
        layout.addWidget(info)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(
            ["Teensy 4.1 Pin", "Signal", "NAND Flash Pin", "Description"]
        )
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setRowCount(len(WIRING_TABLE))
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setVisible(False)

        for row, (teensy, sig, nand, desc) in enumerate(WIRING_TABLE):
            items = [
                QTableWidgetItem(teensy),
                QTableWidgetItem(sig),
                QTableWidgetItem(nand),
                QTableWidgetItem(desc),
            ]
            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col < 3:
                    item.setFont(QFont("Consolas", 9))
                table.setItem(row, col, item)

        layout.addWidget(table)
        return w

    def _build_notes_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)

        notes_text = """<style>
            body { color: #CDD6F4; font-family: Segoe UI; font-size: 10pt; }
            h3   { color: #89B4FA; margin-top: 14px; margin-bottom: 4px; }
            li   { margin-bottom: 5px; }
            code { color: #A6E3A1; font-family: Consolas; background: #313244;
                   padding: 1px 4px; border-radius: 3px; }
        </style>
        <body>
        <h3>⚡ Power Requirements</h3>
        <ul>
          <li>NAND Flash chips require <b>3.3V VCC</b>. Do not apply 5V.</li>
          <li>Use a P-channel MOSFET (e.g., AO3401) on pin 15 (VCC_EN)
              to control chip power. This protects the chip during connection.</li>
          <li>Add 100nF + 10µF decoupling capacitors near the chip VCC pin.</li>
        </ul>
        <h3>📌 Signal Integrity</h3>
        <ul>
          <li>Keep wires short (&lt;15cm) to avoid signal integrity issues.</li>
          <li>Use a ZIF (Zero Insertion Force) socket for TSOP48 chips.</li>
          <li>Add 33Ω series resistors on data bus lines if you see errors.</li>
          <li>R/B# (pin 13) needs a 10kΩ pull-up resistor to 3.3V.</li>
          <li>WP# (pin 14) is driven high by firmware when not write-protected.</li>
        </ul>
        <h3>🔧 Supported Packages</h3>
        <ul>
          <li><code>TSOP48</code>  – Most common (Samsung, Micron, Toshiba)</li>
          <li><code>BGA152/132</code> – Requires BGA adapter socket</li>
          <li><code>LGA52</code>   – eMMC adapter required (not directly supported)</li>
        </ul>
        <h3>⚠ Precautions</h3>
        <ul>
          <li>ESD protection: use anti-static wrist strap and mat.</li>
          <li>Never hot-plug the NAND chip while powered.</li>
          <li>Always use 'Detect Chip' before any read/write operation.</li>
          <li>Back up the chip before any erase or write operation.</li>
        </ul>
        </body>"""

        from PyQt6.QtWidgets import QTextEdit
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setHtml(notes_text)
        txt.setStyleSheet(
            f"background-color: {COLORS['bg_secondary']}; border: none;"
        )
        layout.addWidget(txt)
        return w
