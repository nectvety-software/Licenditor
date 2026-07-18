"""
main_window.py
---------------
Cua so chinh cua ung dung. An title bar OS, dung CustomTitleBar tu ve.
Co tab bar voi 7 tab: Audit, Temp, Uninstall, Delete, Virus, Memory Recovery, Memory Repair, Port.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QGridLayout, QProgressBar, QFileDialog, QScrollArea,
    QGraphicsDropShadowEffect, QStackedWidget, QTextEdit,
)

from app.core import detectors as det
from app.core.scanner import ScanWorker
from app.ui.title_bar import CustomTitleBar
from app.ui.widgets import ResultCard, VerdictBanner
from app.ui.modal import ModalOverlay, ConfirmOverlay, MessageModal, ICONS
from app.ui.tools_ui import (
    TempCleanerPanel, GeekUninstallerPanel,
    DeleteStubbornPanel, VirusScannerPanel,
    MemoryCardRecoveryPanel, MemoryCardRepairPanel,
    PortDetectorPanel, CDriveCleanerPanel, OrphanedAppDataPanel,
    WindowsRepairPanel, FirewallPanel,
    DriverScannerPanel,
)


class KeyCompareWorker(QThread):
    finished = Signal(dict)
    def run(self):
        self.finished.emit(det.compare_bios_windows_keys())


class KeyActivateWorker(QThread):
    finished = Signal(dict)
    def run(self):
        self.finished.emit(det.activate_oem_key())


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("License Integrity Auditor")
        self.resize(1020, 720)
        self.setMinimumSize(QSize(780, 580))

        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._sections: dict[str, det.ScanSection] = {}
        self._cards: dict[str, ResultCard] = {}
        self._worker: ScanWorker | None = None
        self._key_compare_worker: KeyCompareWorker | None = None
        self._key_activate_worker: KeyActivateWorker | None = None

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        self.container = QFrame()
        self.container.setObjectName("AppContainer")
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 200))
        self.container.setGraphicsEffect(shadow)
        outer.addWidget(self.container)

        c_layout = QVBoxLayout(self.container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)

        self.title_bar = CustomTitleBar("License Integrity Auditor - Enterprise Edition")
        self.title_bar.set_target_window(self)
        c_layout.addWidget(self.title_bar)

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 8, 0, 8)
        sidebar_layout.setSpacing(0)

        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(14, 6, 14, 10)
        logo_icon = QLabel(ICONS["shield"])
        logo_icon.setObjectName("SidebarLogo")
        logo_text = QLabel("Tools")
        logo_text.setObjectName("SidebarLogoText")
        logo_row.addWidget(logo_icon)
        logo_row.addWidget(logo_text)
        logo_row.addStretch(1)
        sidebar_layout.addLayout(logo_row)

        sep = QFrame()
        sep.setObjectName("SidebarSep")
        sep.setFixedHeight(1)
        sidebar_layout.addWidget(sep)

        tab_defs = [
            (0, ICONS["shield"], " Ki\u1ec3m tra b\u1ea3n quy\u1ec1n", True),
            (1, ICONS["trash"], " D\u1eefn d\u1eb9p Temp", False),
            (2, ICONS["trash"], " G\u1ee7 ph\u1ea7n m\u1ec1m", False),
            (3, ICONS["trash"], " X\u00f3a c\u01b0\u1eddng \u0111\u1ea7u", False),
            (4, ICONS["shield"], " Qu\u00e9t virus", False),
            (5, ICONS["sdcard"], " Ph\u1ee5c h\u1ed3i th\u1ebb nh\u1edd", False),
            (6, ICONS["sdcard"], " S\u1eefa ch\u1ee9a th\u1ebb nh\u1edd", False),
            (7, ICONS["usb"], " Ph\u00e1t hi\u1ec7n c\u1ed5ng", False),
            (8, ICONS["trash"], " X\u00f3a v\u0129nh vi\u1ec5n", False),
            (9, ICONS["trash"], " AppData s\u00f3t", False),
            (10, ICONS["shield"], " S\u1eeda Windows", False),
            (11, ICONS["shield"], " T\u01b0\u1eddng l\u1eeda", False),
            (12, ICONS["search"], " Qu\u00e9t driver", False),
        ]

        self.tab_buttons = []
        for idx, icon, label, active in tab_defs:
            btn = QPushButton(f"  {icon}  {label}")
            btn.setObjectName("TabButton")
            btn.setProperty("active", active)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self._switch_tab(i))
            sidebar_layout.addWidget(btn)
            self.tab_buttons.append(btn)

        sidebar_layout.addStretch(1)

        ver_label = QLabel("  v1.0 Enterprise")
        ver_label.setObjectName("SidebarVersion")
        sidebar_layout.addWidget(ver_label)

        body_layout.addWidget(sidebar)

        sep2 = QFrame()
        sep2.setObjectName("SidebarSepV")
        sep2.setFixedWidth(1)
        body_layout.addWidget(sep2)

        self.stack = QStackedWidget()
        self.stack.setObjectName("MainStack")

        audit_page = self._build_audit_page()
        self.stack.addWidget(audit_page)
        self.stack.addWidget(TempCleanerPanel())
        self.stack.addWidget(GeekUninstallerPanel())
        self.stack.addWidget(DeleteStubbornPanel())
        self.stack.addWidget(VirusScannerPanel())
        self.stack.addWidget(MemoryCardRecoveryPanel())
        self.stack.addWidget(MemoryCardRepairPanel())
        self.stack.addWidget(PortDetectorPanel())
        self.stack.addWidget(CDriveCleanerPanel())
        self.stack.addWidget(OrphanedAppDataPanel())
        self.stack.addWidget(WindowsRepairPanel())
        self.stack.addWidget(FirewallPanel())
        self.stack.addWidget(DriverScannerPanel())
        body_layout.addWidget(self.stack, 1)

        c_layout.addLayout(body_layout, 1)

        self.detail_modal = ModalOverlay(self.container)
        self.confirm_modal = ConfirmOverlay(self.container)
        self.message_modal = MessageModal(self.container)

    def _build_audit_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setObjectName("ToolScroll")

        page = QWidget()
        pl = QVBoxLayout(page)
        pl.setContentsMargins(24, 14, 24, 16)
        pl.setSpacing(12)

        header_row = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        page_title = QLabel("Ki\u1ec3m tra b\u1ea3n quy\u1ec1n h\u1ec7 th\u1ed1ng")
        page_title.setObjectName("PageTitle")
        page_subtitle = QLabel(
            "\u0110\u1ed1i chi\u1ebfu Windows/Office Activation, kh\u00f3a OEM trong BIOS, registry, "
            "scheduled task, service v\u00e0 t\u1ea1n d\u1eeb c\u01a1ng c\u1ee5 k\u00edch ho\u1ea1t tr\u00e1i ph\u00e9p."
        )
        page_subtitle.setObjectName("PageSubtitle")
        page_subtitle.setWordWrap(True)
        title_col.addWidget(page_title)
        title_col.addWidget(page_subtitle)
        header_row.addLayout(title_col, 1)

        self.export_btn = QPushButton(f"{ICONS['copy']} Xu\u1ea5t b\u00e1o c\u00e1o")
        self.export_btn.setObjectName("SecondaryButton")
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.setEnabled(False)
        header_row.addWidget(self.export_btn, 0, Qt.AlignTop)

        self.scan_btn = QPushButton(f"{ICONS['search']} B\u1eaft \u0111\u1ea7u qu\u00e9t")
        self.scan_btn.setObjectName("PrimaryButton")
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        header_row.addWidget(self.scan_btn, 0, Qt.AlignTop)

        pl.addLayout(header_row)

        self.verdict_banner = VerdictBanner()
        pl.addWidget(self.verdict_banner)

        prog_row = QVBoxLayout()
        prog_row.setSpacing(4)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("ScanProgress")
        self.progress_bar.setRange(0, len(det.ALL_CHECKS))
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)

        self.status_label = QLabel("S\u1eb5n s\u00e0ng qu\u00e9t.")
        self.status_label.setObjectName("ScanStatusLabel")
        self.status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        prog_row.addWidget(self.progress_bar)
        prog_row.addWidget(self.status_label)
        pl.addLayout(prog_row)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("ToolOutput")
        self.log_text.setMaximumHeight(180)
        self.log_text.setPlaceholderText("Nh\u1eadt k\u00fd qu\u00e9t...")
        pl.addWidget(self.log_text)

        bios_frame = QFrame()
        bios_frame.setObjectName("BiosKeyFrame")
        bios_layout = QVBoxLayout(bios_frame)
        bios_layout.setContentsMargins(16, 12, 16, 12)
        bios_layout.setSpacing(8)

        bios_title = QLabel("Kh\u00f3a OEM trong BIOS / Kh\u00f3a hi\u1ec7n t\u1ea1i c\u1ee7a Windows")
        bios_title.setObjectName("BiosKeyTitle")
        bios_layout.addWidget(bios_title)

        key_row = QHBoxLayout()
        key_row.setSpacing(16)

        bios_col = QVBoxLayout()
        bios_col.setSpacing(2)
        bios_col.addWidget(QLabel("Kh\u00f3a OEM trong BIOS:"))
        self.bios_key_value = QLabel("--- Ch\u01b0a qu\u00e9t ---")
        self.bios_key_value.setObjectName("BiosKeyValue")
        self.bios_key_value.setWordWrap(True)
        self.bios_key_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bios_col.addWidget(self.bios_key_value)
        key_row.addLayout(bios_col, 1)

        vs_label = QLabel("VS")
        vs_label.setObjectName("VsLabel")
        vs_label.setAlignment(Qt.AlignCenter)
        key_row.addWidget(vs_label)

        win_col = QVBoxLayout()
        win_col.setSpacing(2)
        win_col.addWidget(QLabel("Kh\u00f3a hi\u1ec7n t\u1ea1i c\u1ee7a Windows:"))
        self.win_key_value = QLabel("--- Ch\u01b0a qu\u00e9t ---")
        self.win_key_value.setObjectName("WinKeyValue")
        self.win_key_value.setWordWrap(True)
        self.win_key_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        win_col.addWidget(self.win_key_value)
        key_row.addLayout(win_col, 1)

        bios_layout.addLayout(key_row)

        self.key_status_label = QLabel("")
        self.key_status_label.setObjectName("KeyStatusLabel")
        self.key_status_label.setWordWrap(True)
        self.key_status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bios_layout.addWidget(self.key_status_label)

        key_btn_row = QHBoxLayout()
        self.compare_key_btn = QPushButton(f"{ICONS['refresh']} So s\u00e1nh kh\u00f3a")
        self.compare_key_btn.setObjectName("SecondaryButton")
        self.compare_key_btn.setCursor(Qt.PointingHandCursor)
        self.compare_key_btn.clicked.connect(self._compare_keys)
        key_btn_row.addWidget(self.compare_key_btn)

        self.activate_key_btn = QPushButton(f"{ICONS['check']} K\u00edch ho\u1ea1t kh\u00f3a OEM BIOS")
        self.activate_key_btn.setObjectName("AccentButton")
        self.activate_key_btn.setCursor(Qt.PointingHandCursor)
        self.activate_key_btn.clicked.connect(self._activate_oem_key)
        key_btn_row.addWidget(self.activate_key_btn)
        key_btn_row.addStretch(1)
        bios_layout.addLayout(key_btn_row)

        pl.addWidget(bios_frame)

        grid_wrap = QFrame()
        self.grid = QGridLayout(grid_wrap)
        self.grid.setSpacing(12)
        for i, key in enumerate(det.ALL_CHECKS):
            label = det.SECTION_LABELS[key]
            card = ResultCard(key, label)
            card.clicked.connect(self._open_detail)
            self._cards[key] = card
            self.grid.addWidget(card, i // 2, i % 2)
        pl.addWidget(grid_wrap)

        pl.addStretch(1)
        scroll.setWidget(page)
        return scroll

    def _switch_tab(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.tab_buttons):
            btn.setProperty("active", i == index)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def resizeEvent(self, event):
        self.detail_modal.setGeometry(self.container.rect())
        self.confirm_modal.setGeometry(self.container.rect())
        self.message_modal.setGeometry(self.container.rect())
        super().resizeEvent(event)

    # ------------------------------------------------------------------ #
    def _compare_keys(self) -> None:
        self.compare_key_btn.setEnabled(False)
        self.compare_key_btn.setText(f"{ICONS['refresh']} \u0110ang so s\u00e1nh...")
        self.key_status_label.setText("\u0110ang truy x\u00fat th\u00f4ng tin kh\u00f3a...")

        self._key_compare_worker = KeyCompareWorker()
        self._key_compare_worker.finished.connect(self._on_compare_done)
        self._key_compare_worker.start()

    def _on_compare_done(self, result: dict) -> None:
        self.compare_key_btn.setEnabled(True)
        self.compare_key_btn.setText(f"{ICONS['refresh']} So s\u00e1nh kh\u00f3a")

        if "error" in result:
            self.key_status_label.setText(f"{ICONS['x']} {result['error']}")
            return

        oem_partial = result.get("oem_partial", "")
        win_partial = result.get("windows_partial", "")
        oem_key = result.get("oem_key", "")

        if oem_key and len(oem_key) > 10:
            display_key = oem_key[:5] + "****-****-****-" + oem_key[-5:]
        else:
            display_key = oem_key or "Kh\u00f4ng t\u00ecm th\u1ea5y"

        self.bios_key_value.setText(f"OA3x: {oem_partial or 'N/A'} (\u0111\u1ea7y \u0111\u1ee7: {display_key})")
        self.win_key_value.setText(f"Partial: {win_partial or 'N/A'} | K\u00eanh: {result.get('windows_channel', 'N/A')}")

        if result.get("keys_match"):
            self.key_status_label.setText(f"{ICONS['check']} Kh\u00f3a OEM BIOS v\u00e0 Windows \u0110\u00c3 KH\u1ed8P. B\u1ea3n quy\u1ec1n h\u1ee3p l\u1ec7.")
            self.key_status_label.setProperty("status", "match")
        else:
            self.key_status_label.setText(
                f"{ICONS['warning']} {result.get('match_detail', 'Kh\u00f3a kh\u00f4ng kh\u1edbp')}. "
                "Nh\u1ea5n \"K\u00edch ho\u1ea1t kh\u00f3a OEM BIOS\" \u0111\u1ec3 s\u1eed d\u1ee5ng kh\u00f3a ch\u00ednh h\u00e3ng."
            )
            self.key_status_label.setProperty("status", "mismatch")

        self.key_status_label.style().unpolish(self.key_status_label)
        self.key_status_label.style().polish(self.key_status_label)

    def _activate_oem_key(self) -> None:
        self.message_modal.confirm(
            "X\u00e1c nh\u1eadn k\u00edch ho\u1ea1t",
            "B\u1ea1n c\u00f3 ch\u1eafc mu\u1ed1n k\u00edch ho\u1ea1t kh\u00f3a OEM BIOS?\n\n"
            "Thao t\u00e1c n\u00e0y s\u1ebd:\n"
            "  - C\u00e0i \u0111\u1eb7t kh\u00f3a OEM t\u1eeb BIOS/UEFI v\u00e0o Windows\n"
            "  - K\u00edch ho\u1ea1t Windows b\u1eb1ng kh\u00f3a ch\u00ednh h\u00e3ng\n"
            "  - Kh\u00f4ng g\u00e2y l\u1ed7i h\u1ec7 \u0111i\u1ec1u h\u00e0nh\n\n"
            "B\u1ea1n c\u00f3 mu\u1ed1n ti\u1ebfp t\u1ee5c?",
            on_yes=self._do_activate,
        )

    def _do_activate(self):
        self.activate_key_btn.setEnabled(False)
        self.activate_key_btn.setText(f"{ICONS['check']} \u0110ang k\u00edch ho\u1ea1t...")
        self.key_status_label.setText("\u0110ang c\u00e0i \u0111\u1eb7t kh\u00f3a OEM v\u00e0 k\u00edch ho\u1ea1t...")

        self._key_activate_worker = KeyActivateWorker()
        self._key_activate_worker.finished.connect(self._on_activate_done)
        self._key_activate_worker.start()

    def _on_activate_done(self, result: dict) -> None:
        self.activate_key_btn.setEnabled(True)
        self.activate_key_btn.setText(f"{ICONS['check']} K\u00edch ho\u1ea1t kh\u00f3a OEM BIOS")

        if result.get("success"):
            self.key_status_label.setText(f"{ICONS['check']} {result.get('message', 'Th\u00e0nh c\u00f4ng!')}")
            self.key_status_label.setProperty("status", "match")
            self.message_modal.success(
                "K\u00edch ho\u1ea1t th\u00e0nh c\u00f4ng",
                f"\u0110\u00e3 c\u00e0i \u0111\u1eb7t v\u00e0 k\u00edch ho\u1ea1t kh\u00f3a OEM BIOS.\n\n"
                f"Kh\u00f3a \u0111\u00e3 d\u00f9ng: ...{result.get('oem_partial', '')}\n"
                f"Tr\u1ea1ng th\u00e1i: {result.get('message', '')}",
            )
        else:
            self.key_status_label.setText(f"{ICONS['x']} {result.get('error', 'L\u1ed7i kh\u00f4ng x\u00e1c \u0111\u1ecbnh')}")
            self.key_status_label.setProperty("status", "error")
            self.message_modal.error(
                "L\u1ed7i k\u00edch ho\u1ea1t",
                f"Kh\u00f4ng th\u1ec3 k\u00edch ho\u1ea1t kh\u00f3a OEM BIOS.\n\n"
                f"L\u1ed7i: {result.get('error', 'Kh\u00f4ng x\u00e1c \u0111\u1ecbnh')}",
            )

        self.key_status_label.style().unpolish(self.key_status_label)
        self.key_status_label.style().polish(self.key_status_label)

    # ------------------------------------------------------------------ #
    def _connect_signals(self) -> None:
        self.title_bar.minimize_clicked.connect(self.showMinimized)
        self.title_bar.maximize_clicked.connect(self._toggle_maximize)
        self.title_bar.close_clicked.connect(self._request_close)

        self.scan_btn.clicked.connect(self._start_scan)
        self.export_btn.clicked.connect(self._export_report)

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
            self.title_bar.btn_max.setText("\u2610")
        else:
            self.showMaximized()
            self.title_bar.btn_max.setText("\u2752")

    def _request_close(self) -> None:
        self.confirm_modal.ask("B\u1ea1n c\u00f3 ch\u1eafc mu\u1ed1n tho\u00e1t \u1ee9ng d\u1ee5ng?", self.close)

    # ------------------------------------------------------------------ #
    def _start_scan(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(f"{ICONS['search']} \u0110ang qu\u00e9t...")
        self.export_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self._sections.clear()
        for card in self._cards.values():
            card.badge.set_state("unknown")
            card.summary.setText("\u0110ang ch\u1edd...")

        self.log_text.clear()
        self.log_text.append(">>> B\u1eaft \u0111\u1ea7u qu\u00e9t ki\u1ec3m tra b\u1ea3n quy\u1ec1n...")
        self.verdict_banner.set_scanning()

        self._worker = ScanWorker()
        self._worker.step_started.connect(self._on_step_started)
        self._worker.step_finished.connect(self._on_step_finished)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_all.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_step_started(self, key: str, label: str) -> None:
        self.status_label.setText(f"\u0110ang ki\u1ec3m tra: {label}...")
        self.log_text.append(f">>> \u0110ang ki\u1ec3m tra: {label}...")

    def _on_step_finished(self, key: str, section: det.ScanSection) -> None:
        self._sections[key] = section
        card = self._cards.get(key)
        if card:
            card.update_from_section(section)
        self.log_text.append(f"  - {section.label}: {section.summary}")

    def _on_progress(self, current: int, total: int) -> None:
        self.progress_bar.setValue(current)

    def _on_finished(self, sections: dict, verdict: str, score: int, desc: str) -> None:
        self._sections = sections
        self.verdict_banner.set_result(verdict, score, desc)
        self.status_label.setText("Ho\u00e0n t\u1ea5t qu\u00e9t l\u00fac " + datetime.now().strftime("%H:%M:%S %d/%m/%Y"))
        self.log_text.append(f">>> Ho\u00e0n t\u1ea5t qu\u00e9t. K\u1ebft lu\u1eadn: {desc}")
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText(f"{ICONS['search']} Qu\u00e9t l\u00e0i")
        self.export_btn.setEnabled(True)

    def _on_failed(self, message: str) -> None:
        self.status_label.setText("L\u1ed7i khi qu\u00e9t: " + message)
        self.log_text.append(f">>> L\u1ed7i: {message}")
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText(f"{ICONS['search']} B\u1eaft \u0111\u1ea7u qu\u00e9t")

    # ------------------------------------------------------------------ #
    def _open_detail(self, key: str) -> None:
        section = self._sections.get(key)
        if section is None:
            section = det.ScanSection(
                key=key,
                label=det.SECTION_LABELS.get(key, key),
                status="unknown",
                summary="Ch\u01b0a c\u00f3 d\u1eef li\u1ec7u - h\u00e3y ch\u1ea1y qu\u00e9t tr\u01b0\u1edbc.",
            )
        self.detail_modal.setGeometry(self.container.rect())
        self.detail_modal.show_section(section)

    # ------------------------------------------------------------------ #
    def _export_report(self) -> None:
        if not self._sections:
            return

        default_name = f"license_audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path, _ = QFileDialog.getSaveFileName(self, "L\u01b0u b\u00e1o c\u00e1o", default_name, "JSON (*.json)")
        if not path:
            return

        data = {
            "generated_at": datetime.now().isoformat(),
            "sections": {
                k: {
                    "label": s.label,
                    "status": s.status,
                    "summary": s.summary,
                    "findings": [f.__dict__ for f in s.findings],
                }
                for k, s in self._sections.items()
            },
        }
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
            self.message_modal.success("Xu\u1ea5t b\u00e1o c\u00e1o", f"\u0110\u00e3 l\u01b0u: {os.path.basename(path)}")
        except OSError as exc:
            self.message_modal.error("L\u1ed7i", f"Kh\u00f4ng th\u1ec3 l\u01b0u b\u00e1o c\u00e1o: {exc}")
