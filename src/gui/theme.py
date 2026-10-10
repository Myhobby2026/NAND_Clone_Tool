"""
Professional Dark Theme Stylesheet
====================================
QSS stylesheet for the NAND Flash Clone Tool.
Inspired by VS Code dark theme with amber accent colors.
"""

DARK_THEME = """
/* ── Global ────────────────────────────────────────────────── */
QWidget {
    background-color: #1E1E2E;
    color: #CDD6F4;
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
    font-size: 10pt;
    selection-background-color: #45475A;
    selection-color: #CDD6F4;
}

QMainWindow {
    background-color: #181825;
}

/* ── Frames & GroupBoxes ───────────────────────────────────── */
QFrame {
    background-color: #1E1E2E;
    border: none;
}

QGroupBox {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    margin-top: 14px;
    padding: 8px 6px 6px 6px;
    font-weight: bold;
    color: #89B4FA;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 2px;
    padding: 0 4px;
    color: #89B4FA;
    font-size: 9pt;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* ── Buttons ───────────────────────────────────────────────── */
QPushButton {
    background-color: #313244;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 5px;
    padding: 6px 16px;
    font-weight: 500;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #45475A;
    border-color: #89B4FA;
    color: #89B4FA;
}
QPushButton:pressed {
    background-color: #181825;
    border-color: #6C7086;
}
QPushButton:disabled {
    background-color: #1E1E2E;
    color: #585B70;
    border-color: #313244;
}

QPushButton#btn_primary {
    background-color: #1E66F5;
    color: #FFFFFF;
    border: none;
    font-weight: 600;
}
QPushButton#btn_primary:hover {
    background-color: #3B7EFF;
}
QPushButton#btn_primary:disabled {
    background-color: #1a3a7a;
    color: #6C7086;
}

QPushButton#btn_success {
    background-color: #40A02B;
    color: #FFFFFF;
    border: none;
    font-weight: 600;
}
QPushButton#btn_success:hover {
    background-color: #4CC32E;
}

QPushButton#btn_danger {
    background-color: #D20F39;
    color: #FFFFFF;
    border: none;
    font-weight: 600;
}
QPushButton#btn_danger:hover {
    background-color: #F2143C;
}
QPushButton#btn_danger:disabled {
    background-color: #5a0818;
    color: #6C7086;
}

QPushButton#btn_warning {
    background-color: #DF8E1D;
    color: #1E1E2E;
    border: none;
    font-weight: 600;
}
QPushButton#btn_warning:hover {
    background-color: #F0A020;
}

/* ── Labels ────────────────────────────────────────────────── */
QLabel {
    background-color: transparent;
    color: #CDD6F4;
}
QLabel#label_title {
    font-size: 20pt;
    font-weight: 700;
    color: #89B4FA;
    letter-spacing: 1px;
}
QLabel#label_subtitle {
    font-size: 10pt;
    color: #6C7086;
}
QLabel#label_value {
    color: #A6E3A1;
    font-weight: 600;
    font-family: "Consolas", "Courier New", monospace;
}
QLabel#label_warning {
    color: #FAB387;
}
QLabel#label_error {
    color: #F38BA8;
}
QLabel#label_section {
    color: #89B4FA;
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    padding-bottom: 2px;
    border-bottom: 1px solid #313244;
}

/* ── ComboBox ──────────────────────────────────────────────── */
QComboBox {
    background-color: #313244;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 24px;
    selection-background-color: #45475A;
}
QComboBox:hover {
    border-color: #89B4FA;
}
QComboBox:focus {
    border-color: #1E66F5;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #45475A;
    border-radius: 0 4px 4px 0;
}
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #CDD6F4;
    border: 1px solid #45475A;
    selection-background-color: #1E66F5;
    outline: none;
}

/* ── LineEdit ──────────────────────────────────────────────── */
QLineEdit {
    background-color: #313244;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 24px;
    font-family: "Consolas", "Courier New", monospace;
}
QLineEdit:focus {
    border-color: #1E66F5;
    background-color: #292941;
}
QLineEdit:read-only {
    background-color: #181825;
    color: #A6ADC8;
}

/* ── SpinBox ───────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {
    background-color: #313244;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 4px;
    padding: 4px 8px;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #1E66F5;
}

/* ── CheckBox / RadioButton ───────────────────────────────── */
QCheckBox, QRadioButton {
    color: #CDD6F4;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #45475A;
    border-radius: 3px;
    background-color: #313244;
}
QCheckBox::indicator:checked {
    background-color: #1E66F5;
    border-color: #1E66F5;
}
QCheckBox::indicator:hover {
    border-color: #89B4FA;
}
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border: 2px solid #45475A;
    border-radius: 7px;
    background-color: #313244;
}
QRadioButton::indicator:checked {
    background-color: #1E66F5;
    border-color: #1E66F5;
}

/* ── ProgressBar ───────────────────────────────────────────── */
QProgressBar {
    background-color: #313244;
    border: 1px solid #45475A;
    border-radius: 4px;
    text-align: center;
    color: #CDD6F4;
    min-height: 18px;
    font-weight: 600;
    font-size: 9pt;
}
QProgressBar::chunk {
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #1E66F5,
        stop:1 #89B4FA
    );
    border-radius: 3px;
}
QProgressBar#progress_erase::chunk {
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #D20F39,
        stop:1 #F38BA8
    );
}
QProgressBar#progress_write::chunk {
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #40A02B,
        stop:1 #A6E3A1
    );
}

/* ── Tabs ──────────────────────────────────────────────────── */
QTabWidget::pane {
    background-color: #1E1E2E;
    border: 1px solid #313244;
    border-radius: 4px;
    top: -1px;
}
QTabWidget::tab-bar {
    alignment: left;
}
QTabBar::tab {
    background-color: #181825;
    color: #6C7086;
    border: 1px solid #313244;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    padding: 7px 18px;
    margin-right: 2px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background-color: #1E1E2E;
    color: #CDD6F4;
    border-bottom: 2px solid #1E66F5;
}
QTabBar::tab:hover:!selected {
    background-color: #313244;
    color: #CDD6F4;
}

/* ── Scroll Bars ───────────────────────────────────────────── */
QScrollBar:vertical {
    background: #181825;
    width: 10px;
    margin: 0;
    border: none;
}
QScrollBar::handle:vertical {
    background: #45475A;
    border-radius: 5px;
    min-height: 30px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #585B70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #181825;
    height: 10px;
    margin: 0;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #45475A;
    border-radius: 5px;
    min-width: 30px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: #585B70;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Table / Tree ──────────────────────────────────────────── */
QTableWidget, QTreeWidget, QListWidget {
    background-color: #181825;
    alternate-background-color: #1E1E2E;
    color: #CDD6F4;
    border: 1px solid #313244;
    border-radius: 4px;
    gridline-color: #313244;
    outline: none;
}
QHeaderView::section {
    background-color: #313244;
    color: #89B4FA;
    padding: 5px 8px;
    border: none;
    border-right: 1px solid #45475A;
    border-bottom: 1px solid #45475A;
    font-weight: 600;
    font-size: 9pt;
    letter-spacing: 0.3px;
}
QTableWidget::item:selected,
QTreeWidget::item:selected,
QListWidget::item:selected {
    background-color: #313244;
    color: #89B4FA;
}
QTableWidget::item:hover,
QTreeWidget::item:hover {
    background-color: #292941;
}

/* ── Text Edit / Plain Text ────────────────────────────────── */
QTextEdit, QPlainTextEdit {
    background-color: #181825;
    color: #CDD6F4;
    border: 1px solid #313244;
    border-radius: 4px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 9pt;
    selection-background-color: #45475A;
}

/* ── Splitter ──────────────────────────────────────────────── */
QSplitter::handle {
    background-color: #313244;
}
QSplitter::handle:horizontal {
    width: 3px;
}
QSplitter::handle:vertical {
    height: 3px;
}
QSplitter::handle:hover {
    background-color: #1E66F5;
}

/* ── Status Bar ────────────────────────────────────────────── */
QStatusBar {
    background-color: #181825;
    color: #A6ADC8;
    border-top: 1px solid #313244;
    font-size: 9pt;
}
QStatusBar::item {
    border: none;
}

/* ── Toolbar ───────────────────────────────────────────────── */
QToolBar {
    background-color: #181825;
    border-bottom: 1px solid #313244;
    spacing: 4px;
    padding: 4px;
}
QToolButton {
    background-color: transparent;
    color: #CDD6F4;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 9pt;
}
QToolButton:hover {
    background-color: #313244;
    border-color: #45475A;
}
QToolButton:pressed {
    background-color: #181825;
}
QToolButton:checked {
    background-color: #1E66F5;
    color: #FFFFFF;
    border-color: #3B7EFF;
}

/* ── Menu Bar ──────────────────────────────────────────────── */
QMenuBar {
    background-color: #181825;
    color: #CDD6F4;
    border-bottom: 1px solid #313244;
    padding: 2px;
}
QMenuBar::item {
    background-color: transparent;
    padding: 4px 10px;
    border-radius: 3px;
}
QMenuBar::item:selected {
    background-color: #313244;
    color: #CDD6F4;
}
QMenuBar::item:pressed {
    background-color: #1E66F5;
    color: #FFFFFF;
}

/* ── Menu ──────────────────────────────────────────────────── */
QMenu {
    background-color: #313244;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 4px;
    padding: 4px;
}
QMenu::item {
    padding: 5px 20px 5px 10px;
    border-radius: 3px;
}
QMenu::item:selected {
    background-color: #1E66F5;
    color: #FFFFFF;
}
QMenu::separator {
    height: 1px;
    background-color: #45475A;
    margin: 3px 5px;
}

/* ── Dialog ────────────────────────────────────────────────── */
QDialog {
    background-color: #1E1E2E;
}

/* ── Tooltip ───────────────────────────────────────────────── */
QToolTip {
    background-color: #313244;
    color: #CDD6F4;
    border: 1px solid #45475A;
    border-radius: 3px;
    padding: 4px 8px;
    font-size: 9pt;
}

/* ── Dock Widget ───────────────────────────────────────────── */
QDockWidget {
    background-color: #1E1E2E;
    titlebar-close-icon: none;
}
QDockWidget::title {
    background-color: #181825;
    color: #89B4FA;
    padding: 5px 8px;
    border-bottom: 1px solid #313244;
    font-weight: 600;
    font-size: 9pt;
    letter-spacing: 0.3px;
    text-transform: uppercase;
}

/* ── Slider ────────────────────────────────────────────────── */
QSlider::groove:horizontal {
    height: 4px;
    background: #313244;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #1E66F5;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::sub-page:horizontal {
    background: #1E66F5;
    border-radius: 2px;
}
"""

# Accent colors for programmatic use
COLORS = {
    "bg_primary":    "#1E1E2E",
    "bg_secondary":  "#181825",
    "bg_tertiary":   "#313244",
    "fg_primary":    "#CDD6F4",
    "fg_secondary":  "#A6ADC8",
    "fg_muted":      "#6C7086",
    "accent_blue":   "#1E66F5",
    "accent_light":  "#89B4FA",
    "accent_green":  "#40A02B",
    "accent_green2": "#A6E3A1",
    "accent_red":    "#D20F39",
    "accent_red2":   "#F38BA8",
    "accent_orange": "#DF8E1D",
    "accent_orange2":"#FAB387",
    "border":        "#313244",
    "border_hover":  "#45475A",
}
