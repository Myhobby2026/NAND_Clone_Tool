"""
Main Window
============
Main application window for the NAND Flash Clone Tool.
Professional dark-themed PyQt6 interface with:
  - Toolbar with connection controls
  - Left panel: device info + bad block visualizer
  - Center: tabbed operation panels (Read/Write/Clone/Erase/Scan)
  - Right panel: log output
  - Bottom: progress bar + status indicators
"""

from __future__ import annotations

import os
import time
import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QLabel, QPushButton,
    QStatusBar, QToolBar, QDockWidget, QMenuBar,
    QMenu, QFileDialog, QMessageBox, QDialog,
    QApplication, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSlot
from PyQt6.QtGui import QIcon, QFont, QAction, QColor, QPalette

from ..core.nand_engine import NANDEngine
from ..models.nand_models import OperationProgress, OperationStatus, DeviceInfo
from .theme import DARK_THEME, COLORS

# Panel imports
from .panels.connection_panel  import ConnectionPanel
from .panels.device_panel      import DeviceInfoPanel
from .panels.read_panel        import ReadPanel
from .panels.write_panel       import WritePanel
from .panels.erase_panel       import ErasePanel
from .panels.clone_panel       import ClonePanel
from .panels.scan_panel        import ScanBadBlocksPanel
from .panels.hex_viewer        import HexViewerPanel
from .panels.block_map_panel   import BlockMapPanel
from .panels.log_panel         import LogPanel
from .panels.settings_panel    import SettingsPanel


class MainWindow(QMainWindow):
    """
    NAND Flash Clone Tool - Main Application Window
    """

    APP_TITLE   = "NAND Flash Clone Tool"
    APP_VERSION = "1.0.0"

    def __init__(self):
        super().__init__()
        self.engine = NANDEngine(self)
        self._init_ui()
        self._connect_engine_signals()
        self._setup_timers()
        self._update_status_idle()

    # ─────────────────────────────────────────────────────────
    #  UI Construction
    # ─────────────────────────────────────────────────────────
    def _init_ui(self):
        self.setWindowTitle(f"{self.APP_TITLE}  v{self.APP_VERSION}")
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)

        # Set Window Icon
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        icon_path = os.path.join(base_dir, "assets", "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(base_dir, "assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._build_menu_bar()
        self._build_toolbar()
        self._build_central()
        self._build_docks()
        self._build_status_bar()

    # ── Menu Bar ──────────────────────────────────────────────
    def _build_menu_bar(self):
        mb = self.menuBar()
        mb.setObjectName("menubar")

        # File
        file_menu = mb.addMenu("&File")
        self._act_open = QAction("&Open Dump File…", self)
        self._act_open.setShortcut("Ctrl+O")
        self._act_open.triggered.connect(self._open_file)
        file_menu.addAction(self._act_open)

        self._act_save = QAction("&Save Dump As…", self)
        self._act_save.setShortcut("Ctrl+S")
        self._act_save.triggered.connect(self._save_file)
        file_menu.addAction(self._act_save)

        file_menu.addSeparator()

        act_export_map = QAction("Export Bad Block Map…", self)
        act_export_map.triggered.connect(self._export_bad_block_map)
        file_menu.addAction(act_export_map)

        act_export_log = QAction("Export Log…", self)
        act_export_log.triggered.connect(self._export_log)
        file_menu.addAction(act_export_log)

        file_menu.addSeparator()

        act_exit = QAction("E&xit", self)
        act_exit.setShortcut("Alt+F4")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # Device
        dev_menu = mb.addMenu("&Device")
        self._act_connect = QAction("&Connect…", self)
        self._act_connect.setShortcut("Ctrl+Shift+C")
        self._act_connect.triggered.connect(self._show_connect_dialog)
        dev_menu.addAction(self._act_connect)

        self._act_disconnect = QAction("&Disconnect", self)
        self._act_disconnect.setEnabled(False)
        self._act_disconnect.triggered.connect(self._disconnect)
        dev_menu.addAction(self._act_disconnect)

        dev_menu.addSeparator()

        act_detect = QAction("Detect NAND Chip", self)
        act_detect.setShortcut("F5")
        act_detect.triggered.connect(self._detect_chip)
        dev_menu.addAction(act_detect)

        act_reset = QAction("Reset NAND", self)
        act_reset.triggered.connect(lambda: self.engine.serial.nand_reset())
        dev_menu.addAction(act_reset)

        dev_menu.addSeparator()

        act_power_on = QAction("Power ON", self)
        act_power_on.triggered.connect(lambda: self.engine.serial.set_power(True))
        dev_menu.addAction(act_power_on)

        act_power_off = QAction("Power OFF", self)
        act_power_off.triggered.connect(lambda: self.engine.serial.set_power(False))
        dev_menu.addAction(act_power_off)

        # Operations
        ops_menu = mb.addMenu("&Operations")
        act_read = QAction("Read Full Dump", self)
        act_read.setShortcut("F6")
        act_read.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
        ops_menu.addAction(act_read)

        act_write = QAction("Write to Chip", self)
        act_write.setShortcut("F7")
        act_write.triggered.connect(lambda: self.tabs.setCurrentIndex(1))
        ops_menu.addAction(act_write)

        act_erase = QAction("Erase Chip", self)
        act_erase.setShortcut("F8")
        act_erase.triggered.connect(lambda: self.tabs.setCurrentIndex(2))
        ops_menu.addAction(act_erase)

        act_clone = QAction("Clone Chip", self)
        act_clone.setShortcut("F9")
        act_clone.triggered.connect(lambda: self.tabs.setCurrentIndex(3))
        ops_menu.addAction(act_clone)

        ops_menu.addSeparator()

        act_cancel = QAction("Cancel Operation", self)
        act_cancel.setShortcut("Escape")
        act_cancel.triggered.connect(self.engine.cancel_operation)
        ops_menu.addAction(act_cancel)

        # View
        view_menu = mb.addMenu("&View")
        act_hex = QAction("Hex Viewer", self)
        act_hex.triggered.connect(lambda: self.tabs.setCurrentWidget(self.hex_viewer))
        view_menu.addAction(act_hex)

        act_map = QAction("Block Map", self)
        act_map.triggered.connect(lambda: self.tabs.setCurrentWidget(self.block_map))
        view_menu.addAction(act_map)

        # Help
        help_menu = mb.addMenu("&Help")
        act_about = QAction("About…", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

        act_hw = QAction("Hardware Wiring Guide…", self)
        act_hw.triggered.connect(self._show_wiring)
        help_menu.addAction(act_hw)

    # ── Toolbar ───────────────────────────────────────────────
    def _build_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setObjectName("main_toolbar")
        tb.setIconSize(QSize(18, 18))
        tb.setMovable(False)
        tb.setFloatable(False)
        self.addToolBar(tb)

        # Connection
        tb.addWidget(QLabel("  Port: "))
        from .panels.connection_panel import PortSelector
        self.port_selector = PortSelector(self)
        self.port_selector.setMinimumWidth(140)
        self.port_selector.setMaximumWidth(200)
        tb.addWidget(self.port_selector)

        self.btn_connect = QPushButton("⟳ Connect")
        self.btn_connect.setObjectName("btn_primary")
        self.btn_connect.setFixedWidth(100)
        self.btn_connect.clicked.connect(self._quick_connect)
        tb.addWidget(self.btn_connect)

        self.btn_disconnect = QPushButton("✕ Disconnect")
        self.btn_disconnect.setObjectName("btn_danger")
        self.btn_disconnect.setFixedWidth(110)
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.clicked.connect(self._disconnect)
        tb.addWidget(self.btn_disconnect)

        tb.addSeparator()

        # Detect
        self.btn_detect = QPushButton("⬡ Detect Chip")
        self.btn_detect.setObjectName("btn_warning")
        self.btn_detect.setFixedWidth(120)
        self.btn_detect.setEnabled(False)
        self.btn_detect.clicked.connect(self._detect_chip)
        tb.addWidget(self.btn_detect)

        tb.addSeparator()

        # Cancel
        self.btn_cancel = QPushButton("⬛ Cancel")
        self.btn_cancel.setObjectName("btn_danger")
        self.btn_cancel.setFixedWidth(90)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self.engine.cancel_operation)
        tb.addWidget(self.btn_cancel)

        tb.addSeparator()

        # Connection indicator LED
        tb.addWidget(QLabel("  Status: "))
        self.lbl_conn_status = QLabel("● Disconnected")
        self.lbl_conn_status.setStyleSheet(f"color: {COLORS['accent_red2']}; font-weight: bold;")
        tb.addWidget(self.lbl_conn_status)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        # Version label
        ver_label = QLabel(f"NAND Flash Clone Tool  v{self.APP_VERSION}  ")
        ver_label.setStyleSheet(f"color: {COLORS['fg_muted']}; font-size: 8pt;")
        tb.addWidget(ver_label)

    # ── Central Widget ────────────────────────────────────────
    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Main splitter: left | center | right
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(3)

        # ── Left Panel ──────────────────────────
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(6, 6, 3, 6)
        left_layout.setSpacing(6)
        left_widget.setMinimumWidth(260)
        left_widget.setMaximumWidth(340)

        self.device_panel = DeviceInfoPanel(self.engine)
        left_layout.addWidget(self.device_panel)

        self.block_map_mini = BlockMapPanel(self.engine, mini=True)
        self.block_map_mini.setMinimumHeight(180)
        self.block_map_mini.setMaximumHeight(220)
        left_layout.addWidget(self.block_map_mini)

        left_layout.addStretch()
        self.main_splitter.addWidget(left_widget)

        # ── Center: Tab Panel ───────────────────
        self.tabs = QTabWidget()
        self.tabs.setObjectName("main_tabs")
        self.tabs.setMinimumWidth(600)

        # Operation panels
        self.read_panel  = ReadPanel(self.engine)
        self.write_panel = WritePanel(self.engine)
        self.erase_panel = ErasePanel(self.engine)
        self.clone_panel = ClonePanel(self.engine)
        self.scan_panel  = ScanBadBlocksPanel(self.engine)
        self.hex_viewer  = HexViewerPanel(self.engine)
        self.block_map   = BlockMapPanel(self.engine, mini=False)
        self.settings_panel = SettingsPanel(self.engine)

        self.tabs.addTab(self.read_panel,      "📥  Read")
        self.tabs.addTab(self.write_panel,     "📤  Write")
        self.tabs.addTab(self.erase_panel,     "🗑  Erase")
        self.tabs.addTab(self.clone_panel,     "⧉  Clone")
        self.tabs.addTab(self.scan_panel,      "🔍  Scan Blocks")
        self.tabs.addTab(self.hex_viewer,      "🔢  Hex View")
        self.tabs.addTab(self.block_map,       "▦  Block Map")
        self.tabs.addTab(self.settings_panel,  "⚙  Settings")

        self.main_splitter.addWidget(self.tabs)

        # ── Right Panel: Log ────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(3, 6, 6, 6)
        right_layout.setSpacing(0)
        right_widget.setMinimumWidth(240)
        right_widget.setMaximumWidth(380)

        self.log_panel = LogPanel()
        right_layout.addWidget(self.log_panel)
        self.main_splitter.addWidget(right_widget)

        # Splitter proportions
        self.main_splitter.setSizes([280, 900, 280])
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)

        main_layout.addWidget(self.main_splitter)

        # ── Bottom Progress Area ────────────────
        progress_bar_widget = self._build_progress_area()
        main_layout.addWidget(progress_bar_widget)

    def _build_progress_area(self) -> QWidget:
        """Build the bottom progress bar area."""
        from PyQt6.QtWidgets import QProgressBar
        
        widget = QFrame()
        widget.setObjectName("progress_area")
        widget.setStyleSheet(f"""
            QFrame#progress_area {{
                background-color: {COLORS['bg_secondary']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)
        widget.setFixedHeight(54)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        # Operation label
        self.lbl_operation = QLabel("Ready")
        self.lbl_operation.setStyleSheet(f"color: {COLORS['fg_secondary']}; min-width: 160px;")
        layout.addWidget(self.lbl_operation)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("main_progress")
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        layout.addWidget(self.progress_bar, stretch=1)

        # Stats labels
        self.lbl_throughput = QLabel("0 KB/s")
        self.lbl_throughput.setStyleSheet(
            f"color: {COLORS['accent_green2']}; font-family: monospace; min-width: 70px;")
        layout.addWidget(self.lbl_throughput)

        self.lbl_eta = QLabel("ETA: --:--")
        self.lbl_eta.setStyleSheet(
            f"color: {COLORS['fg_secondary']}; font-family: monospace; min-width: 80px;")
        layout.addWidget(self.lbl_eta)

        self.lbl_pages = QLabel("0 / 0 pages")
        self.lbl_pages.setStyleSheet(
            f"color: {COLORS['fg_muted']}; font-family: monospace; min-width: 110px;")
        layout.addWidget(self.lbl_pages)

        return widget

    # ── Docks ─────────────────────────────────────────────────
    def _build_docks(self):
        pass  # Log panel is in right splitter pane

    # ── Status Bar ────────────────────────────────────────────
    def _build_status_bar(self):
        sb = self.statusBar()
        sb.setObjectName("main_statusbar")

        # Connection indicator
        self.sb_conn = QLabel("  ● Disconnected  ")
        self.sb_conn.setStyleSheet(f"color: {COLORS['accent_red2']};")
        sb.addPermanentWidget(self.sb_conn)

        sb.addPermanentWidget(self._make_separator())

        # Chip info
        self.sb_chip = QLabel("  No chip detected  ")
        self.sb_chip.setStyleSheet(f"color: {COLORS['fg_muted']};")
        sb.addPermanentWidget(self.sb_chip)

        sb.addPermanentWidget(self._make_separator())

        # ECC status
        self.sb_ecc = QLabel("  ECC: Hamming  ")
        self.sb_ecc.setStyleSheet(f"color: {COLORS['fg_muted']};")
        sb.addPermanentWidget(self.sb_ecc)

        sb.addPermanentWidget(self._make_separator())

        # Throughput
        self.sb_speed = QLabel("  -- KB/s  ")
        self.sb_speed.setStyleSheet(f"color: {COLORS['fg_muted']};")
        sb.addPermanentWidget(self.sb_speed)

        sb.addPermanentWidget(self._make_separator())

        # Clock
        self.sb_clock = QLabel()
        sb.addPermanentWidget(self.sb_clock)

    @staticmethod
    def _make_separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {COLORS['border']}; max-height: 14px;")
        return sep

    # ─────────────────────────────────────────────────────────
    #  Signal Connections
    # ─────────────────────────────────────────────────────────
    def _connect_engine_signals(self):
        e = self.engine
        e.connection_changed.connect(self._on_connection_changed)
        e.device_detected.connect(self._on_device_detected)
        e.operation_started.connect(self._on_op_started)
        e.operation_progress.connect(self._on_op_progress)
        e.operation_completed.connect(self._on_op_completed)
        e.log_message.connect(self._on_log_message)
        e.bad_block_found.connect(self._on_bad_block)

        # Connect sub-panels to engine
        self.read_panel.connect_engine(e)
        self.write_panel.connect_engine(e)
        self.erase_panel.connect_engine(e)
        self.clone_panel.connect_engine(e)
        self.scan_panel.connect_engine(e)
        self.hex_viewer.connect_engine(e)
        self.device_panel.connect_engine(e)
        self.block_map.connect_engine(e)
        self.block_map_mini.connect_engine(e)
        self.settings_panel.connect_engine(e)

    def _setup_timers(self):
        # Clock update
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)

        # Port refresh
        self._port_timer = QTimer(self)
        self._port_timer.timeout.connect(self._refresh_ports)
        self._port_timer.start(3000)

    # ─────────────────────────────────────────────────────────
    #  Slots
    # ─────────────────────────────────────────────────────────
    @pyqtSlot(bool, str)
    def _on_connection_changed(self, connected: bool, message: str):
        if connected:
            self.lbl_conn_status.setText("● Connected")
            self.lbl_conn_status.setStyleSheet(
                f"color: {COLORS['accent_green2']}; font-weight: bold;")
            self.sb_conn.setText(f"  ● Connected: {self.engine.device_info.port}  ")
            self.sb_conn.setStyleSheet(f"color: {COLORS['accent_green2']};")
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
            self.btn_detect.setEnabled(True)
            self._act_disconnect.setEnabled(True)
        else:
            self.lbl_conn_status.setText("● Disconnected")
            self.lbl_conn_status.setStyleSheet(
                f"color: {COLORS['accent_red2']}; font-weight: bold;")
            self.sb_conn.setText("  ● Disconnected  ")
            self.sb_conn.setStyleSheet(f"color: {COLORS['accent_red2']};")
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)
            self.btn_detect.setEnabled(False)
            self._act_disconnect.setEnabled(False)
        self.statusBar().showMessage(message, 4000)

    @pyqtSlot(DeviceInfo)
    def _on_device_detected(self, dev: DeviceInfo):
        chip_str = f"{dev.manufacturer} {dev.model} | {dev.total_size_mb:.0f} MB"
        self.sb_chip.setText(f"  {chip_str}  ")
        self.sb_chip.setStyleSheet(f"color: {COLORS['accent_green2']};")
        if self.engine.ecc:
            self.sb_ecc.setText(f"  ECC: {self.engine.ecc.mode.upper()}  ")
        self.setWindowTitle(
            f"{self.APP_TITLE}  –  {chip_str}  v{self.APP_VERSION}"
        )

    @pyqtSlot(OperationProgress)
    def _on_op_started(self, op: OperationProgress):
        self.btn_cancel.setEnabled(True)
        self.lbl_operation.setText(op.op_type.value)
        self.progress_bar.setValue(0)
        self._set_operation_style(op)
        self.statusBar().showMessage(f"Started: {op.op_type.value}")

    @pyqtSlot(OperationProgress)
    def _on_op_progress(self, op: OperationProgress):
        self.progress_bar.setValue(int(op.percent))
        self.lbl_throughput.setText(f"{op.throughput_kbps:.0f} KB/s")
        self.sb_speed.setText(f"  {op.throughput_kbps:.0f} KB/s  ")
        
        eta = op.eta_seconds
        if eta > 0:
            m, s = divmod(int(eta), 60)
            self.lbl_eta.setText(f"ETA: {m:02d}:{s:02d}")
        
        self.lbl_pages.setText(
            f"{op.current:,} / {op.total:,} "
            f"{'pages' if 'Page' in op.op_type.value or 'Read' in op.op_type.value else 'blocks'}"
        )

    @pyqtSlot(OperationProgress)
    def _on_op_completed(self, op: OperationProgress):
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setValue(100 if op.status == OperationStatus.COMPLETED else 0)
        
        elapsed = op.elapsed_seconds
        m, s = divmod(int(elapsed), 60)

        if op.status == OperationStatus.COMPLETED:
            self.lbl_operation.setText(f"✓ {op.op_type.value} Complete")
            self.statusBar().showMessage(
                f"✓ {op.op_type.value} completed in {m:02d}:{s:02d} "
                f"| {op.ecc_corrected} ECC corrections, {op.ecc_errors} uncorrectable",
                8000
            )
            self.log_panel.add_success(
                f"{op.op_type.value} completed in {m:02d}:{s:02d}"
            )
        elif op.status == OperationStatus.FAILED:
            self.lbl_operation.setText(f"✗ {op.op_type.value} FAILED")
            self.progress_bar.setObjectName("progress_failed")
            errors = "; ".join(op.errors[-3:]) if op.errors else "Unknown error"
            self.statusBar().showMessage(
                f"✗ {op.op_type.value} failed: {errors}", 8000
            )
        elif op.status == OperationStatus.CANCELLED:
            self.lbl_operation.setText(f"Cancelled: {op.op_type.value}")

    @pyqtSlot(str, str)
    def _on_log_message(self, level: str, message: str):
        self.log_panel.add_message(level, message)

    @pyqtSlot(int)
    def _on_bad_block(self, block: int):
        self.log_panel.add_message("warning", f"Bad block found: #{block}")

    def _set_operation_style(self, op: OperationProgress):
        from ..models.nand_models import OperationType
        if op.op_type == OperationType.ERASE_ALL:
            self.progress_bar.setObjectName("progress_erase")
        elif op.op_type in (OperationType.WRITE_FULL_DUMP, OperationType.CLONE):
            self.progress_bar.setObjectName("progress_write")
        else:
            self.progress_bar.setObjectName("main_progress")
        self.progress_bar.setStyleSheet("")  # Force style refresh

    # ─────────────────────────────────────────────────────────
    #  Actions
    # ─────────────────────────────────────────────────────────
    def _quick_connect(self):
        port = self.port_selector.current_port()
        if not port:
            QMessageBox.warning(self, "No Port", "Please select a serial port.")
            return
        self.engine.connect(port)

    def _show_connect_dialog(self):
        from .dialogs.connect_dialog import ConnectDialog
        dlg = ConnectDialog(self.engine, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            pass

    def _disconnect(self):
        if self.engine.is_busy():
            ret = QMessageBox.question(
                self, "Operation Running",
                "An operation is running. Cancel and disconnect?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ret != QMessageBox.StandardButton.Yes:
                return
            self.engine.cancel_operation()
        self.engine.disconnect()
        self.sb_chip.setText("  No chip detected  ")
        self.sb_chip.setStyleSheet(f"color: {COLORS['fg_muted']};")

    def _detect_chip(self):
        if not self.engine.serial.connected:
            QMessageBox.warning(self, "Not Connected",
                                "Connect to the Teensy board first.")
            return
        self.engine.detect_device()

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Dump File", "",
            "NAND Dump Files (*.bin *.img *.nandimg *.raw);;All Files (*)"
        )
        if path:
            self.engine.session.source_file = path
            self.write_panel.set_source_file(path)
            self.hex_viewer.load_file(path)
            self.statusBar().showMessage(f"Opened: {path}", 4000)

    def _save_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Dump File", "",
            "NAND Image (*.nandimg);;Binary Dump (*.bin);;Raw Image (*.img);;All Files (*)"
        )
        if path:
            self.engine.session.output_file = path
            self.read_panel.set_output_file(path)
            self.statusBar().showMessage(f"Output: {path}", 4000)

    def _export_bad_block_map(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Bad Block Map", "", "Text Files (*.txt);;All Files (*)"
        )
        if path:
            bbm = self.engine.bad_block_map
            with open(path, "w") as f:
                f.write(f"# NAND Flash Bad Block Map\n")
                f.write(f"# Generated: {datetime.datetime.now()}\n")
                f.write(f"# Total blocks: {bbm.total_blocks}\n")
                f.write(f"# Bad blocks: {bbm.bad_count}\n\n")
                for blk in sorted(bbm.bad_blocks):
                    f.write(f"{blk}\n")
            self.statusBar().showMessage(f"Bad block map saved: {path}", 4000)

    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Log", "", "Text Files (*.txt);;All Files (*)"
        )
        if path:
            self.log_panel.save_to_file(path)
            self.statusBar().showMessage(f"Log saved: {path}", 4000)

    def _update_clock(self):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.sb_clock.setText(f"  {now}  ")

    def _refresh_ports(self):
        if hasattr(self, "port_selector"):
            self.port_selector.refresh()

    def _update_status_idle(self):
        self.lbl_operation.setText("Ready")
        self.progress_bar.setValue(0)
        self.lbl_throughput.setText("-- KB/s")
        self.lbl_eta.setText("ETA: --:--")
        self.lbl_pages.setText("0 / 0 pages")

    def _show_about(self):
        from .dialogs.about_dialog import AboutDialog
        AboutDialog(self).exec()

    def _show_wiring(self):
        from .dialogs.wiring_dialog import WiringDialog
        WiringDialog(self).exec()

    # ─────────────────────────────────────────────────────────
    #  Close Event
    # ─────────────────────────────────────────────────────────
    def closeEvent(self, event):
        if self.engine.is_busy():
            ret = QMessageBox.question(
                self, "Operation Running",
                "An operation is still running.\nCancel and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ret != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.engine.cancel_operation()

        if self.engine.serial.connected:
            self.engine.serial.set_power(False)
            self.engine.disconnect()

        event.accept()
