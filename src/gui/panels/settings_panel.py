"""
Settings Panel
==============
Application settings and preferences panel.
Allows configuring ECC mode, operation defaults, and UI options.
"""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QComboBox, QCheckBox, QSpinBox,
    QFrame, QLineEdit, QFileDialog, QMessageBox, QTabWidget
)
from PyQt6.QtCore import Qt

from ...core.nand_engine import NANDEngine
from ...core.ecc_engine  import ECCEngine
from ...utils.settings   import AppSettings
from ..theme import COLORS


ECC_MODE_OPTIONS = [
    ("None (no ECC)",          ECCEngine.MODE_NONE),
    ("Hamming (1-bit/256B)",   ECCEngine.MODE_HAMMING),
    ("BCH-4 (4-bit/512B)",     ECCEngine.MODE_BCH4),
    ("BCH-8 (8-bit/512B)",     ECCEngine.MODE_BCH8),
    ("BCH-12 (12-bit/512B)",   ECCEngine.MODE_BCH12),
    ("BCH-24 (24-bit/1KB)",    ECCEngine.MODE_BCH24),
]


class SettingsPanel(QWidget):
    def __init__(self, engine: NANDEngine = None, parent=None):
        super().__init__(parent)
        self.engine   = engine
        self.settings = AppSettings()
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("⚙  Settings & Preferences")
        title.setStyleSheet(
            f"color: {COLORS['accent_blue']}; font-size: 14pt; font-weight: 700;"
        )
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_ecc_tab(),       "ECC")
        tabs.addTab(self._build_operations_tab(), "Operations")
        tabs.addTab(self._build_serial_tab(),     "Serial")
        tabs.addTab(self._build_ui_tab(),         "UI")
        layout.addWidget(tabs, stretch=1)

        sep = QFrame(frameShape=QFrame.Shape.HLine,
                     styleSheet=f"color: {COLORS['border']};")
        layout.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_apply = QPushButton("✓  Apply")
        btn_apply.setObjectName("btn_primary")
        btn_apply.setMinimumWidth(100)
        btn_apply.clicked.connect(self._apply_settings)
        btn_row.addWidget(btn_apply)

        btn_reset = QPushButton("Reset Defaults")
        btn_reset.clicked.connect(self._reset_settings)
        btn_row.addWidget(btn_reset)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    # ── ECC Tab ───────────────────────────────────────────────
    def _build_ecc_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)
        form.setContentsMargins(12, 12, 12, 12)

        self.combo_ecc = QComboBox()
        for label, _ in ECC_MODE_OPTIONS:
            self.combo_ecc.addItem(label)
        form.addRow("ECC Mode:", self.combo_ecc)

        self.chk_ecc_auto = QCheckBox("Auto-select ECC mode based on detected chip")
        self.chk_ecc_auto.setChecked(True)
        form.addRow("", self.chk_ecc_auto)

        info = QLabel(
            "ECC Mode Guide:\n"
            "  • Hamming   — 1-bit correction, SLC chips\n"
            "  • BCH-4/8   — 4–8 bit, MLC chips\n"
            "  • BCH-12/24 — 12–24 bit, TLC/advanced MLC\n"
            "\nHigher BCH modes are slower but more reliable for worn chips."
        )
        info.setStyleSheet(
            f"color: {COLORS['fg_muted']}; font-size: 9pt; "
            f"font-family: Consolas; padding: 6px; "
            f"background-color: {COLORS['bg_secondary']}; border-radius: 4px;"
        )
        info.setWordWrap(True)
        form.addRow(info)
        return w

    # ── Operations Tab ────────────────────────────────────────
    def _build_operations_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)
        form.setContentsMargins(12, 12, 12, 12)

        self.chk_skip_bad     = QCheckBox("Skip bad blocks by default")
        self.chk_verify_write = QCheckBox("Verify chip after write by default")
        self.chk_include_oob  = QCheckBox("Include OOB area in dumps")
        self.chk_erase_first  = QCheckBox("Erase block before writing")

        form.addRow("Bad Blocks:",    self.chk_skip_bad)
        form.addRow("Verify Write:",  self.chk_verify_write)
        form.addRow("OOB Data:",      self.chk_include_oob)
        form.addRow("Pre-Erase:",     self.chk_erase_first)

        return w

    # ── Serial Tab ────────────────────────────────────────────
    def _build_serial_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)
        form.setContentsMargins(12, 12, 12, 12)

        self.chk_auto_detect = QCheckBox("Auto-detect Teensy 4.1 on startup")
        form.addRow("Auto Detect:", self.chk_auto_detect)

        baud_lbl = QLabel("2,000,000 baud  (fixed by firmware)")
        baud_lbl.setStyleSheet(f"color: {COLORS['fg_muted']};")
        form.addRow("Baud Rate:", baud_lbl)

        timeout_row = QHBoxLayout()
        self.spin_timeout = QSpinBox()
        self.spin_timeout.setMinimum(1)
        self.spin_timeout.setMaximum(300)
        self.spin_timeout.setValue(30)
        self.spin_timeout.setSuffix(" s")
        timeout_row.addWidget(self.spin_timeout)
        timeout_row.addStretch()
        form.addRow("Cmd Timeout:", timeout_row)

        return w

    # ── UI Tab ─────────────────────────────────────────────────
    def _build_ui_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)
        form.setContentsMargins(12, 12, 12, 12)

        self.chk_autoscroll = QCheckBox("Auto-scroll log output")
        form.addRow("Log:", self.chk_autoscroll)

        hex_row = QHBoxLayout()
        self.combo_hex_cols = QComboBox()
        self.combo_hex_cols.addItems(["8", "16", "32"])
        self.combo_hex_cols.setCurrentText("16")
        hex_row.addWidget(self.combo_hex_cols)
        hex_row.addStretch()
        form.addRow("Hex Viewer Cols:", hex_row)

        return w

    # ── Load / Save ───────────────────────────────────────────
    def connect_engine(self, engine: NANDEngine):
        self.engine = engine

    def _load_settings(self):
        s = self.settings

        ecc_mode = s.ecc_mode
        ecc_idx  = next(
            (i for i, (_, m) in enumerate(ECC_MODE_OPTIONS) if m == ecc_mode), 1
        )
        self.combo_ecc.setCurrentIndex(ecc_idx)
        self.chk_ecc_auto.setChecked(s.get_bool("ecc/auto_select"))
        self.chk_skip_bad.setChecked(s.skip_bad_blocks)
        self.chk_verify_write.setChecked(s.verify_after_write)
        self.chk_include_oob.setChecked(s.get_bool("ops/include_oob"))
        self.chk_erase_first.setChecked(True)
        self.chk_auto_detect.setChecked(s.get_bool("serial/auto_detect"))
        self.chk_autoscroll.setChecked(s.get_bool("ui/autoscroll_log"))
        self.combo_hex_cols.setCurrentText(str(s.get_int("ui/hex_cols") or 16))

    def _apply_settings(self):
        s = self.settings

        ecc_idx  = self.combo_ecc.currentIndex()
        ecc_mode = ECC_MODE_OPTIONS[ecc_idx][1] if ecc_idx < len(ECC_MODE_OPTIONS) else "hamming"
        s.ecc_mode       = ecc_mode
        s.set("ecc/auto_select",     self.chk_ecc_auto.isChecked())
        s.skip_bad_blocks  = self.chk_skip_bad.isChecked()
        s.verify_after_write = self.chk_verify_write.isChecked()
        s.set("ops/include_oob",     self.chk_include_oob.isChecked())
        s.set("serial/auto_detect",  self.chk_auto_detect.isChecked())
        s.set("ui/autoscroll_log",   self.chk_autoscroll.isChecked())
        s.set("ui/hex_cols",         int(self.combo_hex_cols.currentText()))
        s.sync()

        # Apply ECC to live engine
        if self.engine and self.engine.device_info.page_size > 0:
            self.engine.ecc = ECCEngine(
                mode      = ecc_mode,
                page_size = self.engine.device_info.page_size,
                oob_size  = self.engine.device_info.oob_size
            )

        QMessageBox.information(self, "Settings", "Settings saved.")

    def _reset_settings(self):
        ret = QMessageBox.question(
            self, "Reset Settings",
            "Reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ret == QMessageBox.StandardButton.Yes:
            self.settings.reset_all()
            self._load_settings()
