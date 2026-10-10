"""
NAND Flash Clone Tool - Application Entry Point
================================================
Professional NAND Flash Memory Clone Tool for Windows.
Hardware: Teensy 4.1 USB serial bridge.
GUI: PyQt6 dark-themed modern interface.

Usage:
    python main.py
    python main.py --port COM5
    python main.py --port COM5 --debug
"""

from __future__ import annotations

import sys
import os
import argparse
import logging

# Ensure the project root is in sys.path
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _parse_args():
    parser = argparse.ArgumentParser(
        prog="NAND Flash Clone Tool",
        description="Professional NAND Flash Memory Clone Tool for Windows"
    )
    parser.add_argument(
        "--port", "-p",
        type=str,
        default="",
        help="Serial port (e.g. COM5). If not given, auto-detect Teensy."
    )
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable DEBUG level logging"
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="Disable log file output"
    )
    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version and exit"
    )
    return parser.parse_args()


def main():
    args = _parse_args()

    if args.version:
        print("NAND Flash Clone Tool v1.0.0")
        sys.exit(0)

    # ── Qt Application ────────────────────────────────────────
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore    import Qt, QCoreApplication
    from PyQt6.QtGui     import QFont, QIcon

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("NANDTools.NANDFlashCloneTool.1.0")
        except Exception:
            pass

    # High DPI support (enabled by default in Qt6)
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    app.setApplicationName("NAND Flash Clone Tool")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("NANDTools")

    # Set application icon
    icon_path = os.path.join(_ROOT, "assets", "icon.ico")
    if not os.path.exists(icon_path):
        icon_path = os.path.join(_ROOT, "assets", "icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # ── Setup Logging ─────────────────────────────────────────
    from src.utils.settings import setup_logging, AppSettings
    level = "DEBUG" if args.debug else "INFO"
    setup_logging(level, enable_file=not args.no_log_file)
    logger = logging.getLogger("nand_flash_tool")

    # ── Load Settings ─────────────────────────────────────────
    settings = AppSettings()

    # ── Apply Theme ───────────────────────────────────────────
    from src.gui.theme import DARK_THEME
    app.setStyleSheet(DARK_THEME)
    
    # Set application-wide monospace font fallback
    default_font = QFont("Segoe UI", 10)
    app.setFont(default_font)

    # ── Show Splash Screen ─────────────────────────────────────
    splash = _create_splash()
    if splash:
        splash.show()
        app.processEvents()

    # ── Build Main Window ─────────────────────────────────────
    from src.gui.main_window import MainWindow
    window = MainWindow()

    # Restore geometry
    geometry = settings.get("ui/window_geometry")
    state    = settings.get("ui/window_state")
    if geometry:
        window.restoreGeometry(geometry)
    if state:
        window.restoreState(state)

    # ── Auto-connect if port given ───────────────────────────
    if args.port:
        logger.info("Auto-connecting to %s", args.port)
        # Defer until event loop starts
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, lambda: window.engine.connect(args.port))
    elif settings.get_bool("serial/auto_detect"):
        from src.core.serial_manager import SerialManager
        teensy_port = SerialManager.find_teensy_port()
        if teensy_port:
            logger.info("Auto-detected Teensy on %s", teensy_port)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, lambda: window.engine.connect(teensy_port))

    # ── Show Window ───────────────────────────────────────────
    if splash:
        import time
        time.sleep(0.8)
        splash.finish(window)

    window.show()
    window.raise_()
    window.activateWindow()

    # ── Event Loop ────────────────────────────────────────────
    exit_code = app.exec()

    # ── Save Settings on Exit ──────────────────────────────────
    settings.set("ui/window_geometry", window.saveGeometry())
    settings.set("ui/window_state",    window.saveState())
    settings.sync()

    logger.info("Application exiting with code %d", exit_code)
    sys.exit(exit_code)


def _create_splash():
    """Create a simple splash screen."""
    try:
        from PyQt6.QtWidgets import QSplashScreen, QLabel, QVBoxLayout, QWidget
        from PyQt6.QtCore    import Qt
        from PyQt6.QtGui     import QPixmap, QPainter, QColor, QFont, QLinearGradient

        # Build splash pixmap programmatically
        w, h  = 480, 290
        pixmap = QPixmap(w, h)
        pixmap.fill(QColor("#181825"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Gradient border
        gradient = QLinearGradient(0, 0, w, h)
        gradient.setColorAt(0.0, QColor("#1E66F5"))
        gradient.setColorAt(1.0, QColor("#40A02B"))
        from PyQt6.QtGui import QPen
        pen = QPen(gradient, 3)
        painter.setPen(pen)
        painter.drawRoundedRect(2, 2, w - 4, h - 4, 8, 8)

        # App Icon
        icon_path = os.path.join(_ROOT, "assets", "icon_64.png")
        if os.path.exists(icon_path):
            icon_pix = QPixmap(icon_path)
            painter.drawPixmap((w - 64) // 2, 22, icon_pix)

        # Title
        painter.setPen(QColor("#89B4FA"))
        font = QFont("Segoe UI", 20, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(0, 95, w, 40, Qt.AlignmentFlag.AlignCenter, "NAND Flash Clone Tool")

        # Subtitle
        painter.setPen(QColor("#6C7086"))
        font2 = QFont("Segoe UI", 10)
        painter.setFont(font2)
        painter.drawText(0, 140, w, 28, Qt.AlignmentFlag.AlignCenter,
                         "Professional NAND Flash Programmer  v1.0.0")

        # Hardware info
        painter.setPen(QColor("#45475A"))
        font3 = QFont("Consolas", 9)
        painter.setFont(font3)
        painter.drawText(0, 180, w, 25, Qt.AlignmentFlag.AlignCenter,
                         "Teensy 4.1  ·  2 Mbaud  ·  CRC-16  ·  Hamming/BCH ECC")

        # Loading
        painter.setPen(QColor("#1E66F5"))
        font4 = QFont("Segoe UI", 9)
        painter.setFont(font4)
        painter.drawText(0, 240, w, 25, Qt.AlignmentFlag.AlignCenter,
                         "Initializing…")

        painter.end()

        splash = QSplashScreen(pixmap)
        splash.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.SplashScreen
        )
        return splash
    except Exception:
        return None


if __name__ == "__main__":
    main()
