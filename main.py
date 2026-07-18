"""
License Integrity Auditor
==========================
Ứng dụng desktop (PySide6) kiểm tra chuyên sâu tình trạng bản quyền
Windows/Office: đối chiếu trạng thái kích hoạt, khóa OEM trong BIOS,
registry, scheduled task, service và tàn dư công cụ kích hoạt trái phép,
để phát hiện các trường hợp hiển thị "Activated" nhưng thực chất là crack.

Chạy: python main.py
Khuyến nghị: chạy với quyền Administrator để đọc đầy đủ registry/BIOS.
"""

from __future__ import annotations

import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QFile, QTextStream
from PySide6.QtGui import QFont

from app.ui.main_window import MainWindow
from app.ui.modal import ICON_FONT, _ensure_font

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STYLE_PATH = os.path.join(BASE_DIR, "app", "resources", "style.qss")


def load_stylesheet(app: QApplication) -> None:
    qss_file = QFile(STYLE_PATH)
    if qss_file.open(QFile.ReadOnly | QFile.Text):
        stream = QTextStream(qss_file)
        app.setStyleSheet(stream.readAll())
        qss_file.close()


def _setup_icon_font(app: QApplication) -> None:
    """Đặt Material Icons làm font dự phòng để icon hiển thị đúng."""
    font = app.font()
    families = [font.family(), ICON_FONT, "Segoe UI", "Arial"]
    font.setFamilies(families)
    app.setFont(font)

def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("License Integrity Auditor")
    _ensure_font()
    _setup_icon_font(app)
    load_stylesheet(app)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
