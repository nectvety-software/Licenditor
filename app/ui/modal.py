"""
modal.py
--------
Hộp thoại "modal" tùy chỉnh, KHÔNG dùng QDialog gốc của hệ điều hành.
Bao gồm: ModalOverlay (chi tiết), ConfirmOverlay (xác nhận),
MessageModal (thông báo/tín lỗi/cảnh báo thay QMessageBox).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QEasingCurve, QPropertyAnimation, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QGraphicsDropShadowEffect, QSizePolicy, QApplication,
)
from PySide6.QtGui import QColor, QFont

from PySide6.QtGui import QFontDatabase

from app.core.detectors import ScanSection, Finding


# --------------------------------------------------------------------------- #
# Icon helper - dùng Google Material Icons font
# --------------------------------------------------------------------------- #

import os as _os
_RES_DIR = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "app", "resources")
_MATERIAL_TTF = _os.path.join(_RES_DIR, "MaterialIcons-Regular.ttf")
_FONT_LOADED = False

def _ensure_font():
    global _FONT_LOADED
    if _FONT_LOADED:
        return
    if _os.path.isfile(_MATERIAL_TTF):
        try:
            fid = QFontDatabase.addApplicationFont(_MATERIAL_TTF)
            if fid >= 0:
                families = QFontDatabase.applicationFontFamilies(fid)
                if families:
                    globals()["ICON_FONT"] = families[0]
        except RuntimeError:
            pass
    _FONT_LOADED = True

ICON_FONT = "Material Icons"

ICONS = {
    "info":     "\uE88E",
    "warning":  "\uE002",
    "error":    "\uE000",
    "success":  "\uE5CA",
    "question": "\uE887",
    "close":    "\uE5CD",
    "trash":    "\uE872",
    "search":   "\uE8B6",
    "refresh":  "\uE5D5",
    "copy":     "\uE14D",
    "folder":   "\uE2C7",
    "usb":      "\uE1E0",
    "sdcard":   "\uE60F",
    "shield":   "\uE9E5",
    "arrow_r":  "\uE5CC",
    "settings": "\uE8B8",
    "check":    "\uE5CA",
    "x":        "\uE5CD",
}


def icon_label(icon_key: str, size: int = 14, color: str = "#c9d1d9") -> QLabel:
    """Tạo QLabel chứa icon từ Google Material Icons."""
    _ensure_font()
    lbl = QLabel(ICONS.get(icon_key, "?"))
    font = QFont(ICON_FONT, size)
    lbl.setFont(font)
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


# --------------------------------------------------------------------------- #
# Finding row
# --------------------------------------------------------------------------- #

class _FindingRow(QFrame):
    def __init__(self, finding: Finding, parent=None):
        super().__init__(parent)
        self.setObjectName("FindingRow")
        self.setProperty("severity", finding.severity)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(3)

        title = QLabel(finding.title)
        title.setObjectName("FindingTitle")
        title.setWordWrap(True)

        detail = QLabel(finding.detail)
        detail.setObjectName("FindingDetail")
        detail.setWordWrap(True)

        lay.addWidget(title)
        lay.addWidget(detail)


# --------------------------------------------------------------------------- #
# MessageModal - thay thế QMessageBox
# --------------------------------------------------------------------------- #

class MessageModal(QWidget):
    """
    Hộp thoại thông báo tùy chỉnh.
    Types: "info" | "warning" | "error" | "success" | "confirm"
    """
    confirmed = Signal()
    cancelled = Signal()

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("ModalOverlay")
        self.hide()
        self._on_confirm = None
        self._on_cancel = None

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        self.panel = QFrame()
        self.panel.setObjectName("ModalPanel")
        self.panel.setFixedWidth(420)

        shadow = QGraphicsDropShadowEffect(self.panel)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.panel.setGraphicsEffect(shadow)

        lay = QVBoxLayout(self.panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        title_bar = QWidget()
        title_bar.setObjectName("ModalTitleBar")
        title_bar.setFixedHeight(42)
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(16, 0, 10, 0)

        self.title_label = QLabel("")
        self.title_label.setObjectName("ModalTitleText")
        tb_layout.addWidget(self.title_label)
        tb_layout.addStretch(1)

        close_btn = QPushButton(ICONS["close"])
        close_btn.setObjectName("ModalCloseBtn")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self._on_close_clicked)
        tb_layout.addWidget(close_btn)
        lay.addWidget(title_bar)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 16)
        body_layout.setSpacing(12)

        self._msg_row = QHBoxLayout()
        self._msg_row.setSpacing(12)

        self.icon_lbl = icon_label("info", 28, "#58a6ff")
        self._msg_row.addWidget(self.icon_lbl, 0, Qt.AlignTop)

        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        self.msg.setObjectName("MessageModalText")
        self._msg_row.addWidget(self.msg, 1)
        body_layout.addLayout(self._msg_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.cancel_btn = QPushButton("Hủy")
        self.cancel_btn.setObjectName("SecondaryButton")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._on_close_clicked)

        self.ok_btn = QPushButton("Đồng ý")
        self.ok_btn.setObjectName("PrimaryButton")
        self.ok_btn.setCursor(Qt.PointingHandCursor)
        self.ok_btn.clicked.connect(self._on_ok_clicked)

        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.ok_btn)
        body_layout.addLayout(btn_row)

        lay.addWidget(body)
        root.addWidget(self.panel)

        self._opacity_anim = None

    def resizeEvent(self, event):
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if not self.panel.geometry().contains(event.position().toPoint()):
            self._on_close_clicked()

    def _on_ok_clicked(self):
        self.hide_animated()
        if callable(self._on_confirm):
            self._on_confirm()
        self.confirmed.emit()

    def _on_close_clicked(self):
        self.hide_animated()
        if callable(self._on_cancel):
            self._on_cancel()
        self.cancelled.emit()

    def show_message(self, title: str, message: str, msg_type: str = "info",
                     on_confirm=None, on_cancel=None, ok_text: str = "Đồng ý",
                     cancel_text: str = "Hủy", show_cancel: bool = True) -> None:
        self.title_label.setText(title)
        self.msg.setText(message)
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self.ok_btn.setText(ok_text)
        self.cancel_btn.setText(cancel_text)
        self.cancel_btn.setVisible(show_cancel)

        icon_map = {
            "info": ("info", "#58a6ff"),
            "warning": ("warning", "#d29922"),
            "error": ("error", "#f85149"),
            "success": ("success", "#3fb950"),
            "confirm": ("question", "#58a6ff"),
        }
        icon_key, icon_color = icon_map.get(msg_type, ("info", "#58a6ff"))
        new_icon = icon_label(icon_key, 28, icon_color)
        old_icon = self.icon_lbl
        if old_icon is not None:
            idx = self._msg_row.indexOf(old_icon)
            if idx >= 0:
                self._msg_row.removeWidget(old_icon)
                old_icon.setParent(None)
                old_icon.deleteLater()
            self._msg_row.insertWidget(0, new_icon)
        self.icon_lbl = new_icon

        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()

    def info(self, title: str, message: str, on_ok=None) -> None:
        self.show_message(title, message, "info", on_confirm=on_ok, show_cancel=False, ok_text="OK")

    def warning(self, title: str, message: str, on_ok=None) -> None:
        self.show_message(title, message, "warning", on_confirm=on_ok, show_cancel=False, ok_text="OK")

    def error(self, title: str, message: str, on_ok=None) -> None:
        self.show_message(title, message, "error", on_confirm=on_ok, show_cancel=False, ok_text="OK")

    def success(self, title: str, message: str, on_ok=None) -> None:
        self.show_message(title, message, "success", on_confirm=on_ok, show_cancel=False, ok_text="OK")

    def confirm(self, title: str, message: str, on_yes=None, on_no=None,
                yes_text: str = "Đồng ý", no_text: str = "Hủy") -> None:
        self.show_message(title, message, "confirm", on_confirm=on_yes, on_cancel=on_no,
                          ok_text=yes_text, cancel_text=no_text, show_cancel=True)

    def danger_confirm(self, title: str, message: str, on_yes=None, on_no=None,
                       yes_text: str = "Tôi hiểu, xoá", no_text: str = "Hủy") -> None:
        self.show_message(title, message, "error", on_confirm=on_yes, on_cancel=on_no,
                          ok_text=yes_text, cancel_text=no_text, show_cancel=True)
        self.ok_btn.setObjectName("DangerButton")
        self.ok_btn.style().unpolish(self.ok_btn)
        self.ok_btn.style().polish(self.ok_btn)

    def show_animated(self) -> None:
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self._opacity_anim.setDuration(160)
        self._opacity_anim.setStartValue(0.0)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._opacity_anim.start()

    def hide_animated(self) -> None:
        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self._opacity_anim.setDuration(120)
        self._opacity_anim.setStartValue(1.0)
        self._opacity_anim.setEndValue(0.0)
        self._opacity_anim.setEasingCurve(QEasingCurve.InCubic)
        self._opacity_anim.finished.connect(self.hide)
        self._opacity_anim.start()


# --------------------------------------------------------------------------- #
# ModalOverlay - chi tiết section
# --------------------------------------------------------------------------- #

class ModalOverlay(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("ModalOverlay")
        self.hide()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(Qt.AlignCenter)

        self.panel = QFrame(self)
        self.panel.setObjectName("ModalPanel")
        self.panel.setFixedWidth(520)
        self.panel.setMaximumHeight(560)

        shadow = QGraphicsDropShadowEffect(self.panel)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.panel.setGraphicsEffect(shadow)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        title_bar = QWidget()
        title_bar.setObjectName("ModalTitleBar")
        title_bar.setFixedHeight(46)
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(16, 0, 10, 0)

        self.title_label = QLabel("")
        self.title_label.setObjectName("ModalTitleText")
        tb_layout.addWidget(self.title_label)
        tb_layout.addStretch(1)

        close_btn = QPushButton(ICONS["close"])
        close_btn.setObjectName("ModalCloseBtn")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.hide_animated)
        tb_layout.addWidget(close_btn)

        panel_layout.addWidget(title_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(16, 14, 16, 16)
        self.content_layout.setSpacing(8)
        self.content_layout.addStretch(1)
        self.scroll.setWidget(self.content)

        panel_layout.addWidget(self.scroll, 1)
        root.addWidget(self.panel)

        self._opacity_anim = None

    def resizeEvent(self, event):
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.panel.setMaximumHeight(max(280, self.parentWidget().height() - 120)
                                     if self.parentWidget() else 560)
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if not self.panel.geometry().contains(event.position().toPoint()):
            self.hide_animated()

    def show_section(self, section: ScanSection) -> None:
        self.title_label.setText(section.label)

        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        summary = QLabel(section.summary)
        summary.setObjectName("CardSummary")
        summary.setWordWrap(True)
        self.content_layout.insertWidget(0, summary)

        if not section.findings:
            empty = QLabel("Không có chi tiết bổ sung.")
            empty.setObjectName("CardSummary")
            self.content_layout.insertWidget(1, empty)
        else:
            for i, f in enumerate(section.findings, start=1):
                self.content_layout.insertWidget(i, _FindingRow(f))

        self.show_animated()

    def show_animated(self) -> None:
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self._opacity_anim.setDuration(160)
        self._opacity_anim.setStartValue(0.0)
        self._opacity_anim.setEndValue(1.0)
        self._opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._opacity_anim.start()

    def hide_animated(self) -> None:
        self._opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        self._opacity_anim.setDuration(120)
        self._opacity_anim.setStartValue(1.0)
        self._opacity_anim.setEndValue(0.0)
        self._opacity_anim.setEasingCurve(QEasingCurve.InCubic)
        self._opacity_anim.finished.connect(self.hide)
        self._opacity_anim.start()


# --------------------------------------------------------------------------- #
# ConfirmOverlay
# --------------------------------------------------------------------------- #

class ConfirmOverlay(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("ModalOverlay")
        self.hide()
        self._on_confirm = None

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        panel = QFrame()
        panel.setObjectName("ModalPanel")
        panel.setFixedWidth(360)

        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 180))
        panel.setGraphicsEffect(shadow)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(14)

        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        self.msg.setObjectName("CardTitle")
        lay.addWidget(self.msg)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton("Hủy")
        cancel.setObjectName("SecondaryButton")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.hide)

        ok = QPushButton("Đồng ý")
        ok.setObjectName("DangerButton")
        ok.setCursor(Qt.PointingHandCursor)
        ok.clicked.connect(self._confirm)

        btn_row.addWidget(cancel)
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)

        root.addWidget(panel)

    def resizeEvent(self, event):
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        super().resizeEvent(event)

    def ask(self, message: str, on_confirm) -> None:
        self.msg.setText(message)
        self._on_confirm = on_confirm
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()

    def _confirm(self):
        self.hide()
        if callable(self._on_confirm):
            self._on_confirm()
