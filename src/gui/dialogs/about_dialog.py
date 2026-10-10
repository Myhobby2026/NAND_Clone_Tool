"""About Dialog."""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QIcon
from ..theme import COLORS


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About NAND Flash Clone Tool")
        self.setFixedSize(480, 400)
        self.setModal(True)
        
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.icon_path = os.path.join(base_dir, "assets", "icon_64.png")
        if os.path.exists(self.icon_path):
            self.setWindowIcon(QIcon(self.icon_path))

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(8)

        # Icon
        if os.path.exists(self.icon_path):
            icon_lbl = QLabel()
            icon_lbl.setPixmap(QPixmap(self.icon_path))
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon_lbl)

        # Title
        title = QLabel("NAND Flash Clone Tool")
        title.setStyleSheet(
            f"color: {COLORS['accent_blue']}; font-size: 18pt; font-weight: 700;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version = QLabel("Version 1.0.0")
        version.setStyleSheet(
            f"color: {COLORS['fg_muted']}; font-size: 10pt;"
        )
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        sep = QFrame(frameShape=QFrame.Shape.HLine,
                     styleSheet=f"color: {COLORS['border']}; margin: 6px 0;")
        layout.addWidget(sep)

        desc = QLabel(
            "Professional NAND Flash Memory Clone Tool\n"
            "for Windows with Teensy 4.1 hardware bridge.\n\n"
            "Supports SLC/MLC/TLC NAND Flash chips from\n"
            "Samsung, Micron, Toshiba, SK Hynix, Macronix, and Nanya.\n\n"
            "Features: Read, Write, Erase, Clone, Bad Block Scan,\n"
            "Hamming/BCH ECC, Hex Viewer, Block Map Visualization."
        )
        desc.setStyleSheet(f"color: {COLORS['fg_secondary']}; font-size: 9pt;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addStretch()

        sep2 = QFrame(frameShape=QFrame.Shape.HLine,
                      styleSheet=f"color: {COLORS['border']};")
        layout.addWidget(sep2)

        hw_info = QLabel(
            "Hardware: Teensy 4.1  (ARM Cortex-M7 @ 600MHz)\n"
            "Protocol: Custom binary serial @ 2 Mbaud with CRC-16"
        )
        hw_info.setStyleSheet(
            f"color: {COLORS['fg_muted']}; font-size: 8pt;"
            f"font-family: 'Consolas', monospace;"
        )
        hw_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hw_info)

        btn = QPushButton("OK")
        btn.setObjectName("btn_primary")
        btn.setFixedWidth(80)
        btn.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)
