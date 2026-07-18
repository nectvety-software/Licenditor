"""
widgets.py
----------
Các thành phần UI tái sử dụng: thẻ kết quả từng hạng mục quét (ResultCard)
và banner kết luận tổng thể (VerdictBanner).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect,
)
from PySide6.QtGui import QColor

from app.core.detectors import ScanSection

_STATE_TEXT = {
    "clean": "AN TOÀN",
    "warning": "NGHI VẤN",
    "danger": "VI PHẠM",
    "unknown": "CHỜ QUÉT",
}


def _style_refresh(widget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class Badge(QLabel):
    def __init__(self, state: str = "unknown", parent=None):
        super().__init__(_STATE_TEXT.get(state, "?"), parent)
        self.setObjectName("Badge")
        self.setProperty("state", state)
        self.setAlignment(Qt.AlignCenter)

    def set_state(self, state: str) -> None:
        self.setText(_STATE_TEXT.get(state, "?"))
        self.setProperty("state", state)
        _style_refresh(self)


class ResultCard(QFrame):
    clicked = Signal(str)  # phát ra key của section khi bấm "Xem chi tiết"

    def __init__(self, key: str, label: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.setObjectName("ResultCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(108)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        top_row = QHBoxLayout()
        title = QLabel(label)
        title.setObjectName("CardTitle")
        top_row.addWidget(title)
        top_row.addStretch(1)
        self.badge = Badge("unknown")
        top_row.addWidget(self.badge)
        outer.addLayout(top_row)

        self.summary = QLabel("Chưa quét.")
        self.summary.setObjectName("CardSummary")
        self.summary.setWordWrap(True)
        outer.addWidget(self.summary)

        outer.addStretch(1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch(1)
        self.detail_btn = QPushButton("Xem chi tiết  →")
        self.detail_btn.setObjectName("SecondaryButton")
        self.detail_btn.setCursor(Qt.PointingHandCursor)
        self.detail_btn.clicked.connect(lambda: self.clicked.emit(self.key))
        bottom_row.addWidget(self.detail_btn)
        outer.addLayout(bottom_row)

    def update_from_section(self, section: ScanSection) -> None:
        self.badge.set_state(section.status)
        self.summary.setText(section.summary or "Không có dữ liệu.")

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.key)
        super().mouseReleaseEvent(event)


class VerdictBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VerdictBanner")
        self.setProperty("verdict", "idle")
        self.setMinimumHeight(96)

        row = QHBoxLayout(self)
        row.setContentsMargins(22, 16, 22, 16)
        row.setSpacing(18)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        self.title = QLabel("Chưa quét hệ thống")
        self.title.setObjectName("VerdictTitle")
        self.desc = QLabel("Bấm \"Bắt đầu quét\" để kiểm tra tình trạng bản quyền thực tế.")
        self.desc.setObjectName("VerdictDesc")
        self.desc.setWordWrap(True)
        text_col.addWidget(self.title)
        text_col.addWidget(self.desc)
        row.addLayout(text_col, 1)

        self.score_label = QLabel("--")
        self.score_label.setObjectName("VerdictScore")
        self.score_label.setAlignment(Qt.AlignCenter)
        row.addWidget(self.score_label)

    def set_result(self, verdict: str, score: int, desc: str) -> None:
        titles = {
            "genuine": "✅ BẢN QUYỀN HỢP LỆ",
            "suspect": "⚠️ NGHI VẤN - CẦN KIỂM TRA THÊM",
            "cracked": "⛔ VI PHẠM BẢN QUYỀN (CRACK)",
        }
        self.title.setText(titles.get(verdict, "Không xác định"))
        self.desc.setText(desc)
        self.score_label.setText(str(score))
        self.setProperty("verdict", verdict)
        _style_refresh(self)

    def set_scanning(self) -> None:
        self.title.setText("🔍 Đang quét hệ thống...")
        self.desc.setText("Đang đối chiếu Windows/Office, BIOS, registry, task scheduler và dấu vết hệ thống.")
        self.score_label.setText("…")
        self.setProperty("verdict", "idle")
        _style_refresh(self)
