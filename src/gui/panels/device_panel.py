"""Device Info Panel - displays detected NAND chip information."""

from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout,
    QPushButton, QFrame, QHBoxLayout
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont

from ...core.nand_engine import NANDEngine
from ...models.nand_models import DeviceInfo
from ..theme import COLORS


def _info_row(label: str, value: str = "--") -> tuple[QLabel, QLabel]:
    lbl = QLabel(label + ":")
    lbl.setStyleSheet(f"color: {COLORS['fg_muted']}; font-size: 9pt;")
    val = QLabel(value)
    val.setStyleSheet(
        f"color: {COLORS['accent_green2']}; "
        f"font-family: 'Consolas', monospace; font-size: 9pt; font-weight: 600;"
    )
    val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lbl, val


class DeviceInfoPanel(QWidget):
    """Left-side panel showing detected NAND chip details."""

    def __init__(self, engine: NANDEngine = None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # ── Header ───────────────────────────────────────────
        hdr = QFrame()
        hdr.setStyleSheet(
            f"background-color: {COLORS['bg_secondary']};"
            f"border-radius: 6px;"
        )
        hdr_layout = QVBoxLayout(hdr)
        hdr_layout.setContentsMargins(10, 8, 10, 8)

        title = QLabel("Device Information")
        title.setStyleSheet(
            f"color: {COLORS['accent_blue']};"
            f"font-size: 10pt; font-weight: 700; letter-spacing: 0.5px;"
        )
        hdr_layout.addWidget(title)

        self.lbl_chip_name = QLabel("No chip detected")
        self.lbl_chip_name.setStyleSheet(
            f"color: {COLORS['fg_primary']}; font-size: 11pt; font-weight: 600;"
        )
        self.lbl_chip_name.setWordWrap(True)
        hdr_layout.addWidget(self.lbl_chip_name)

        self.lbl_density = QLabel("--")
        self.lbl_density.setStyleSheet(
            f"color: {COLORS['fg_muted']}; font-size: 9pt;"
        )
        hdr_layout.addWidget(self.lbl_density)

        layout.addWidget(hdr)

        # ── Identity ──────────────────────────────────────────
        id_grp = QGroupBox("Identity")
        id_form = QFormLayout(id_grp)
        id_form.setSpacing(4)
        id_form.setContentsMargins(8, 12, 8, 8)

        _, self.val_mfr_id   = _info_row("Mfr ID")
        _, self.val_dev_id   = _info_row("Dev ID")
        _, self.val_id_bytes = _info_row("ID Bytes")
        _, self.val_onfi     = _info_row("ONFI")
        
        id_form.addRow("Mfr ID:",    self.val_mfr_id)
        id_form.addRow("Dev ID:",    self.val_dev_id)
        id_form.addRow("ID Bytes:",  self.val_id_bytes)
        id_form.addRow("ONFI:",      self.val_onfi)
        layout.addWidget(id_grp)

        # ── Geometry ─────────────────────────────────────────
        geo_grp = QGroupBox("Geometry")
        geo_form = QFormLayout(geo_grp)
        geo_form.setSpacing(4)
        geo_form.setContentsMargins(8, 12, 8, 8)

        _, self.val_page_size  = _info_row("Page Size")
        _, self.val_oob_size   = _info_row("OOB Size")
        _, self.val_ppb        = _info_row("Pages/Block")
        _, self.val_bpl        = _info_row("Blocks/LUN")
        _, self.val_luns       = _info_row("LUNs")
        _, self.val_total_mb   = _info_row("Total Size")

        geo_form.addRow("Page Size:",   self.val_page_size)
        geo_form.addRow("OOB Size:",    self.val_oob_size)
        geo_form.addRow("Pages/Block:", self.val_ppb)
        geo_form.addRow("Blocks/LUN:",  self.val_bpl)
        geo_form.addRow("LUNs:",        self.val_luns)
        geo_form.addRow("Total Size:",  self.val_total_mb)
        layout.addWidget(geo_grp)

        # ── Status ────────────────────────────────────────────
        st_grp = QGroupBox("Hardware Status")
        st_form = QFormLayout(st_grp)
        st_form.setSpacing(4)
        st_form.setContentsMargins(8, 12, 8, 8)

        _, self.val_wp     = _info_row("Write Prot.")
        _, self.val_fw_ver = _info_row("Firmware")
        _, self.val_ecc    = _info_row("ECC Mode")

        st_form.addRow("Write Prot.:", self.val_wp)
        st_form.addRow("Firmware:",    self.val_fw_ver)
        st_form.addRow("ECC Mode:",    self.val_ecc)
        layout.addWidget(st_grp)

        # ── Detect Button ─────────────────────────────────────
        self.btn_detect = QPushButton("⬡  Detect / Refresh")
        self.btn_detect.setObjectName("btn_warning")
        self.btn_detect.setEnabled(False)
        layout.addWidget(self.btn_detect)

    def connect_engine(self, engine: NANDEngine):
        self.engine = engine
        engine.device_detected.connect(self._on_device_detected)
        engine.connection_changed.connect(self._on_connection_changed)
        self.btn_detect.clicked.connect(engine.detect_device)

    @pyqtSlot(DeviceInfo)
    def _on_device_detected(self, dev: DeviceInfo):
        self.lbl_chip_name.setText(f"{dev.manufacturer}\n{dev.model}")
        density_mb = dev.total_size_mb
        if density_mb >= 1024:
            size_str = f"{density_mb/1024:.2f} GB"
        else:
            size_str = f"{density_mb:.0f} MB"
        self.lbl_density.setText(size_str)

        self.val_mfr_id.setText(f"0x{dev.mfr_id:02X} ({dev.manufacturer})")
        self.val_dev_id.setText(f"0x{dev.dev_id:02X}")
        self.val_id_bytes.setText(
            " ".join(f"{b:02X}" for b in dev.id_bytes[:5])
        )
        self.val_onfi.setText("Yes ✓" if dev.onfi_compliant else "No")
        self.val_page_size.setText(f"{dev.page_size:,} B")
        self.val_oob_size.setText(f"{dev.oob_size} B")
        self.val_ppb.setText(str(dev.pages_per_block))
        self.val_bpl.setText(f"{dev.blocks_per_lun:,}")
        self.val_luns.setText(str(dev.luns))
        self.val_total_mb.setText(
            f"{density_mb:.0f} MB  ({dev.total_pages:,} pages)"
        )
        self.val_wp.setText("Protected ⚠" if dev.write_protected else "Not Protected ✓")
        self.val_wp.setStyleSheet(
            f"color: {COLORS['accent_orange2'] if dev.write_protected else COLORS['accent_green2']};"
            f"font-family: 'Consolas', monospace; font-size: 9pt; font-weight: 600;"
        )
        self.val_fw_ver.setText(dev.firmware_ver)
        if self.engine and self.engine.ecc:
            self.val_ecc.setText(self.engine.ecc.mode.upper())

    @pyqtSlot(bool, str)
    def _on_connection_changed(self, connected: bool, _msg: str):
        self.btn_detect.setEnabled(connected)
        if connected and self.engine:
            self.val_fw_ver.setText(
                self.engine.device_info.firmware_ver
            )
