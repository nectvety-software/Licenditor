"""
title_bar.py
------------
Thanh tiêu đề tùy chỉnh (custom title bar) để thay thế Native Window
Title Bar của hệ điều hành. Hỗ trợ kéo-thả di chuyển cửa sổ, double-click
để phóng to/thu nhỏ, và 3 nút Minimize / Maximize-Restore / Close style
riêng theo QSS.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy


class CustomTitleBar(QWidget):
    minimize_clicked = Signal()
    maximize_clicked = Signal()
    close_clicked = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(40)

        self._drag_pos: QPoint | None = None
        self._target_window: QWidget | None = None  # cửa sổ top-level cần kéo

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 0, 0)
        layout.setSpacing(8)

        icon = QLabel("🛡")
        icon.setObjectName("TitleBarIcon")
        layout.addWidget(icon)

        text = QLabel(title)
        text.setObjectName("TitleBarText")
        layout.addWidget(text)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(spacer)

        self.btn_min = QPushButton("—")
        self.btn_min.setObjectName("TitleBarBtn")
        self.btn_min.setCursor(Qt.PointingHandCursor)
        self.btn_min.clicked.connect(self.minimize_clicked.emit)

        self.btn_max = QPushButton("☐")
        self.btn_max.setObjectName("TitleBarBtn")
        self.btn_max.setCursor(Qt.PointingHandCursor)
        self.btn_max.clicked.connect(self.maximize_clicked.emit)

        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("TitleBarCloseBtn")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.close_clicked.emit)

        for b in (self.btn_min, self.btn_max, self.btn_close):
            layout.addWidget(b)

    def set_target_window(self, window: QWidget) -> None:
        """Cửa sổ top-level thực sự cần được di chuyển/maximize khi thao tác thanh này."""
        self._target_window = window

    # ---- Kéo thả để di chuyển cửa sổ (vì đã ẩn title bar gốc của OS) ----
    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self._target_window is not None:
            self._drag_pos = event.globalPosition().toPoint() - self._target_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton and self._target_window is not None:
            if self._target_window.isMaximized():
                return
            self._target_window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.maximize_clicked.emit()
