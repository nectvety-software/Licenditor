"""
tools_ui.py
-----------
Tab UI cho các công cụ: Temp Cleaner, Geek Uninstaller, Delete Stubborn,
Virus Scanner, Memory Card Recovery/Repair, Port Detector.
Dùng Segoe MDL2 Assets icon font thay cho emoji.
"""

from __future__ import annotations

import os
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QProgressBar, QScrollArea, QLineEdit, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFileDialog, QComboBox,
)
from PySide6.QtGui import QFont, QTextCursor

from app.core import tools
from app.ui.modal import ICONS, ICON_FONT, icon_label, MessageModal


def _icon_btn(text: str, icon_key: str = "", style: str = "PrimaryButton") -> QPushButton:
    """Tạo QPushButton với icon Google Material Icons hiển thị đúng font."""
    from app.ui.modal import _ensure_font
    _ensure_font()
    full = f"{ICONS.get(icon_key, '')} {text}" if icon_key else text
    btn = QPushButton(full)
    btn.setObjectName(style)
    btn.setCursor(Qt.PointingHandCursor)
    font = btn.font()
    families = [ICON_FONT, font.family(), "Segoe UI", "Arial"]
    btn.setFont(font)
    return btn


# --------------------------------------------------------------------------- #
# Worker Threads
# --------------------------------------------------------------------------- #

class TempScanWorker(QThread):
    finished = Signal(list)
    def run(self):
        self.finished.emit(tools.get_temp_locations())

class ProgramListWorker(QThread):
    finished = Signal(list)
    def run(self):
        self.finished.emit(tools.list_installed_programs())

class UninstallWorker(QThread):
    finished = Signal(dict)
    def __init__(self, program: dict):
        super().__init__()
        self.program = program
    def run(self):
        self.finished.emit(tools.uninstall_and_clean(self.program))

class ScanLeftoverWorker(QThread):
    finished = Signal(list)
    def __init__(self, program: dict):
        super().__init__()
        self.program = program
    def run(self):
        self.finished.emit(tools.scan_leftovers(self.program))

class VirusScanWorker(QThread):
    finished = Signal(dict)
    def run(self):
        self.finished.emit(tools.scan_with_windows_defender())

class PortScanWorker(QThread):
    finished = Signal(dict)
    def run(self):
        self.finished.emit(tools.detect_all_external_ports())

class DriveScanWorker(QThread):
    finished = Signal(list)
    def run(self):
        self.finished.emit(tools.detect_removable_drives())

class CDriveScanWorker(QThread):
    finished = Signal(list)
    def run(self):
        self.finished.emit(tools.get_c_drive_cleanable_folders())

class SfcWorker(QThread):
    finished = Signal(dict)
    def run(self):
        self.finished.emit(tools.run_sfc())

class DismScanWorker(QThread):
    finished = Signal(dict)
    def run(self):
        self.finished.emit(tools.run_dism_scanhealth())

class DismRestoreWorker(QThread):
    finished = Signal(dict)
    def run(self):
        self.finished.emit(tools.run_dism())

class ChkdskWorker(QThread):
    finished = Signal(dict)
    def __init__(self, drive: str = "C:"):
        super().__init__()
        self.drive = drive
    def run(self):
        self.finished.emit(tools.run_chkdsk(self.drive))

class FirewallStatusWorker(QThread):
    finished = Signal(dict)
    def run(self):
        self.finished.emit(tools.get_firewall_status())

class FirewallToggleWorker(QThread):
    finished = Signal(dict)
    def __init__(self, on: bool):
        super().__init__()
        self.on = on
    def run(self):
        self.finished.emit(tools.set_firewall(self.on))

class OrphanedAppDataWorker(QThread):
    finished = Signal(list)
    def run(self):
        self.finished.emit(tools.scan_orphaned_appdata())

class OrphanedDeleteWorker(QThread):
    progress = Signal(int, int, str)
    finished = Signal(int, int, list)
    def __init__(self, items: list[dict]):
        super().__init__()
        self.items = items
    def run(self):
        total = len(self.items)
        deleted = 0
        freed = 0
        failed = []
        for i, item in enumerate(self.items):
            path = item["path"]
            self.progress.emit(i + 1, total, path)
            result = tools.clean_leftover({"type": "folder", "path": path})
            if result.get("success"):
                deleted += 1
                freed += item.get("size_bytes", 0)
            else:
                failed.append(item)
        self.finished.emit(deleted, freed, failed)


class DriverScanWorker(QThread):
    finished = Signal(list)
    def run(self):
        self.finished.emit(tools.scan_drivers())


# --------------------------------------------------------------------------- #
# Base Tool Panel
# --------------------------------------------------------------------------- #

class ToolPanel(QWidget):
    def __init__(self, title: str, subtitle: str, icon_key: str = "settings", parent=None):
        super().__init__(parent)
        self.setObjectName("ToolPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("ToolHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 14, 20, 12)
        header_layout.setSpacing(10)

        header_icon = icon_label(icon_key, 20, "#58a6ff")
        header_layout.addWidget(header_icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("ToolTitle")
        subtitle_lbl = QLabel(subtitle)
        subtitle_lbl.setObjectName("ToolSubtitle")
        subtitle_lbl.setWordWrap(True)
        text_col.addWidget(title_lbl)
        text_col.addWidget(subtitle_lbl)
        header_layout.addLayout(text_col, 1)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setObjectName("ToolScroll")

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(20, 14, 20, 14)
        self.content_layout.setSpacing(10)

        scroll.setWidget(self.content)
        layout.addWidget(scroll, 1)

    def _make_icon_btn(self, icon_key: str, text: str, style: str = "PrimaryButton") -> QPushButton:
        full = f"{ICONS.get(icon_key, '')}  {text}"
        btn = QPushButton(full)
        btn.setObjectName(style)
        btn.setCursor(Qt.PointingHandCursor)
        font = btn.font()
        font.setFamilies([ICON_FONT, font.family(), "Segoe UI", "Arial"])
        btn.setFont(font)
        return btn


# --------------------------------------------------------------------------- #
# Temp Cleaner Panel
# --------------------------------------------------------------------------- #

class TempCleanerPanel(ToolPanel):
    def __init__(self, parent=None):
        super().__init__("D\u1ecdn d\u1eb9p file t\u1ea1m", "X\u00f3a file t\u1ea1m, cache, logs \u0111\u1ec3 gi\u1ea3i ph\u00f3ng dung l\u01b0\u1ee3ng.", "trash", parent)
        self._locations = []

        btn_row = QHBoxLayout()
        self.scan_btn = self._make_primary_btn(ICONS["search"], " Qu\u00e9t th\u01b0 m\u1ee5c t\u1ea1m")
        self.scan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self.scan_btn)

        self.clean_all_btn = self._make_danger_btn(ICONS["trash"], " X\u00f3a t\u1ea5t c\u1ea3")
        self.clean_all_btn.setEnabled(False)
        self.clean_all_btn.clicked.connect(self._clean_all)
        btn_row.addWidget(self.clean_all_btn)
        btn_row.addStretch(1)
        self.content_layout.addLayout(btn_row)

        self.status_label = QLabel("Nh\u1ea5n \"Qu\u00e9t\" \u0111\u1ec3 b\u1eaft \u0111\u1ea7u.")
        self.status_label.setObjectName("ToolStatusLabel")
        self.content_layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setObjectName("ScanProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.content_layout.addWidget(self.progress)

        self.table = self._make_table(["Thư mục", "Đường dẫn", "Số file", "Dung lượng"])
        self.content_layout.addWidget(self.table, 1)

        self.result_label = QLabel("")
        self.result_label.setObjectName("ToolResultLabel")
        self.result_label.hide()
        self.content_layout.addWidget(self.result_label)

        self.log_text = self._make_log_area()
        self.content_layout.addWidget(self.log_text)

    def _make_primary_btn(self, icon: str, text: str) -> QPushButton:
        btn = QPushButton(f"{icon} {text}")
        btn.setObjectName("PrimaryButton")
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def _make_danger_btn(self, icon: str, text: str) -> QPushButton:
        btn = QPushButton(f"{icon} {text}")
        btn.setObjectName("DangerButton")
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    def _make_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        for i in range(len(headers)):
            mode = QHeaderView.Stretch if i == 1 else QHeaderView.ResizeToContents
            table.horizontalHeader().setSectionResizeMode(i, mode)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setObjectName("ToolTable")
        return table

    def _make_log_area(self) -> QTextEdit:
        log = QTextEdit()
        log.setReadOnly(True)
        log.setObjectName("ToolOutput")
        log.setMaximumHeight(120)
        log.setPlaceholderText("Nhật ký hoạt động...")
        return log

    def _start_scan(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(f"{ICONS['search']} \u0110ang qu\u00e9t...")
        self.clean_all_btn.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        self.table.setRowCount(0)
        self.log_text.clear()
        self.log_text.append("B\u1eaft \u0111\u1ea7u qu\u00e9t th\u01b0 m\u1ee5c t\u1ea1m...")

        self._worker = TempScanWorker()
        self._worker.finished.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self, locations):
        self._locations = locations
        self.table.setRowCount(len(locations))
        total_size = 0
        for row, loc in enumerate(locations):
            self.table.setItem(row, 0, QTableWidgetItem(loc["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(loc["path"]))
            self.table.setItem(row, 2, QTableWidgetItem(str(loc["file_count"])))
            size_str = self._fmt(loc["size_bytes"])
            self.table.setItem(row, 3, QTableWidgetItem(size_str))
            total_size += loc["size_bytes"]
            self.log_text.append(f"  {loc['name']}: {loc['file_count']} file, {size_str}")

        self.progress.setValue(100)
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText(f"{ICONS['search']} Qu\u00e9t l\u1ea1i")
        self.clean_all_btn.setEnabled(bool(locations))
        self.status_label.setText(f"T\u00ecm th\u1ea5y {len(locations)} th\u01b0 m\u1ee5c. T\u1ed5ng: {self._fmt(total_size)}")
        self.log_text.append(f"Ho\u00e0n t\u1ea5t. T\u00ecm th\u1ea5y {len(locations)} th\u01b0 m\u1ee5c t\u1ea1m.")

    def _clean_all(self):
        if not self._locations:
            return
        self.clean_all_btn.setEnabled(False)
        self.clean_all_btn.setText(f"{ICONS['trash']} \u0110ang x\u00f3a...")
        self.log_text.append("B\u1eaft \u0111\u1ea7u d\u1eefn d\u1ebdp...")
        total_freed = 0
        total_deleted = 0
        for loc in self._locations:
            result = tools.clean_temp_folder(loc["path"])
            total_freed += result["freed"]
            total_deleted += result["deleted"]
            self.log_text.append(f"  {loc['name']}: x\u00f3a {result['deleted']} m\u1ee5c")

        self.result_label.setText(f"\u0110\u00e3 x\u00f3a {total_deleted} m\u1ee5c. Gi\u1ea3i ph\u00f3ng: {self._fmt(total_freed)}")
        self.result_label.show()
        self.clean_all_btn.setText(f"{ICONS['trash']} X\u00f3a t\u1ea5t c\u1ea3")
        self.status_label.setText("Xong!")
        self.log_text.append(f"Ho\u00e0n t\u1ea5t. \u0110\u00e3 x\u00f3a {total_deleted} m\u1ee5c, gi\u1ea3i ph\u00f3ng {self._fmt(total_freed)}")
        self._start_scan()

    def _fmt(self, b: int) -> str:
        for u in ["B", "KB", "MB", "GB"]:
            if b < 1024:
                return f"{b:.1f} {u}"
            b /= 1024
        return f"{b:.1f} TB"


# --------------------------------------------------------------------------- #
# Geek Uninstaller Panel
# --------------------------------------------------------------------------- #

class GeekUninstallerPanel(ToolPanel):
    def __init__(self, parent=None):
        super().__init__("G\u1ee1 b\u1ecf ph\u1ea7n m\u1ec1m", "G\u1ee1 s\u1ea1ch: ch\u1ea1y uninstaller + t\u1ef1 \u0111\u1ed9ng qu\u00e9t v\u00e0 x\u00f3a file/registry s\u00f3t trong AppData, ProgramData.", "trash", parent)
        self._programs = []
        self._leftovers = []

        btn_row = QHBoxLayout()
        self.refresh_btn = _icon_btn("L\u00e0m m\u1edbi", "refresh", "PrimaryButton")
        self.refresh_btn.clicked.connect(self._start_list)
        btn_row.addWidget(self.refresh_btn)

        self.uninstall_btn = _icon_btn("G\u1ee1 \u0111\u00e3 ch\u1ecdn", "trash", "DangerButton")
        self.uninstall_btn.setEnabled(False)
        self.uninstall_btn.clicked.connect(self._uninstall_selected)
        btn_row.addWidget(self.uninstall_btn)

        self.scan_btn = _icon_btn("Qu\u00e9t leftover", "search", "SecondaryButton")
        self.scan_btn.setEnabled(False)
        self.scan_btn.clicked.connect(self._scan_leftovers)
        btn_row.addWidget(self.scan_btn)

        self.clean_btn = _icon_btn("X\u00f3a leftover", "trash", "DangerButton")
        self.clean_btn.setEnabled(False)
        self.clean_btn.clicked.connect(self._clean_leftovers)
        btn_row.addWidget(self.clean_btn)
        btn_row.addStretch(1)
        self.content_layout.addLayout(btn_row)

        self.search = QLineEdit()
        self.search.setPlaceholderText("T\u00ecm ki\u1ebfm ph\u1ea7n m\u1ec1m...")
        self.search.setObjectName("ToolSearch")
        self.search.textChanged.connect(self._filter)
        self.content_layout.addWidget(self.search)

        self.status_label = QLabel("Nh\u1ea5n \"L\u00e0m m\u1edbi\" \u0111\u1ec3 t\u1ea3i danh s\u00e1ch.")
        self.status_label.setObjectName("ToolStatusLabel")
        self.content_layout.addWidget(self.status_label)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["T\u00ean", "Phi\u00ean b\u1ea3n", "Nh\u00e0 ph\u00e1t h\u00e0nh", "Dung l\u01b0\u1ee3ng"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setObjectName("ToolTable")
        self.table.itemSelectionChanged.connect(self._on_sel)
        self.content_layout.addWidget(self.table, 1)

        leftover_label = QLabel("D\u1eef li\u1ec7u s\u00f3t l\u1ea1i (AppData, Registry):")
        leftover_label.setObjectName("ToolStatusLabel")
        self.content_layout.addWidget(leftover_label)

        self.leftover_table = QTableWidget()
        self.leftover_table.setColumnCount(4)
        self.leftover_table.setHorizontalHeaderLabels(["Lo\u1ea1i", "Ngu\u1ed3n", "\u0110\u01b0\u1eddng d\u1eabn", "Dung l\u01b0\u1ee3ng"])
        self.leftover_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.leftover_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.leftover_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.leftover_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.leftover_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.leftover_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.leftover_table.verticalHeader().setVisible(False)
        self.leftover_table.setObjectName("ToolTable")
        self.leftover_table.setMaximumHeight(160)
        self.content_layout.addWidget(self.leftover_table)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("ToolOutput")
        self.log_text.setMaximumHeight(100)
        self.log_text.setPlaceholderText("Nh\u1eadt k\u00fd g\u1ee1 b\u1ecf...")
        self.content_layout.addWidget(self.log_text)

    def _start_list(self):
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText(f"{ICONS['refresh']} \u0110ang t\u1ea3i...")
        self.table.setRowCount(0)
        self.leftover_table.setRowCount(0)
        self.scan_btn.setEnabled(False)
        self.clean_btn.setEnabled(False)
        self.log_text.append("\u0110ang t\u1ea3i danh s\u00e1ch ph\u1ea7n m\u1ec1m...")
        self._worker = ProgramListWorker()
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_done(self, programs):
        self._programs = programs
        self._populate(programs)
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText(f"{ICONS['refresh']} L\u00e0m m\u1edbi")
        self.status_label.setText(f"T\u00ecm th\u1ea5y {len(programs)} ch\u01b0\u01a1ng tr\u00ecnh.")
        self.log_text.append(f"T\u1ea3i xong: {len(programs)} ch\u01b0\u01a1ng tr\u00ecnh.")

    def _populate(self, programs):
        self.table.setRowCount(len(programs))
        for r, p in enumerate(programs):
            self.table.setItem(r, 0, QTableWidgetItem(p["name"]))
            self.table.setItem(r, 1, QTableWidgetItem(p.get("version", "")))
            self.table.setItem(r, 2, QTableWidgetItem(p.get("publisher", "")))
            kb = p.get("size_kb", 0)
            s = f"{kb/1024:.1f} MB" if kb > 1024 else (f"{kb} KB" if kb else "N/A")
            self.table.setItem(r, 3, QTableWidgetItem(s))

    def _filter(self, text):
        if not text:
            self._populate(self._programs)
            return
        self._populate([p for p in self._programs if text.lower() in p["name"].lower()])

    def _on_sel(self):
        has_sel = bool(self.table.selectedItems())
        self.uninstall_btn.setEnabled(has_sel)
        self.scan_btn.setEnabled(has_sel)

    def _uninstall_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name = self.table.item(row, 0).text()
        prog = next((p for p in self._programs if p["name"] == name), None)
        if not prog:
            return
        self._pending_uninstall = prog
        self._pending_name = name
        parent = self.window()
        if hasattr(parent, 'message_modal'):
            parent.message_modal.confirm(
                "X\u00e1c nh\u1eadn g\u1ee1 b\u1ecf",
                f"B\u1ea1n c\u00f3 ch\u1eafc mu\u1ed1n g\u1ee1 b\u1ecf: {name}?\n\n"
                "Sau khi g\u1ee1, s\u1ebd t\u1ef1 \u0111\u1ed9ng qu\u00e9t v\u00e0 x\u00f3a d\u1eef li\u1ec7u s\u00f3t l\u1ea1i\n"
                "trong AppData, ProgramData v\u00e0 Registry.",
                on_yes=self._do_uninstall,
                yes_text="G\u1ee1 b\u1ecf + d\u1ecdn s\u1ea1ch",
                no_text="H\u1ee7y",
            )

    def _do_uninstall(self):
        prog = getattr(self, '_pending_uninstall', None)
        name = getattr(self, '_pending_name', '')
        if not prog:
            return
        self.log_text.append(f"\u0110ang g\u1ee1 b\u1ecf + d\u1ecdn s\u1ea1ch: {name}...")
        self.uninstall_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        worker = UninstallWorker(prog)
        worker.finished.connect(lambda r: self._on_uninstall_done(r, name))
        worker.start()

    def _on_uninstall_done(self, result, name):
        uninstall_result = result.get("uninstall", {})
        leftovers = result.get("leftovers", [])
        leftover_results = result.get("leftover_results", {})
        parent = self.window()

        self.log_text.append(f"K\u1ebft qu\u1ea3 g\u1ee1 {name}: {'OK' if uninstall_result.get('success') else uninstall_result.get('error', 'L\u1ed7i')}")

        self._leftovers = leftovers
        self.leftover_table.setRowCount(len(leftovers))
        total_leftover_size = 0
        for r, item in enumerate(leftovers):
            self.leftover_table.setItem(r, 0, QTableWidgetItem(item["type"]))
            self.leftover_table.setItem(r, 1, QTableWidgetItem(item["source"]))
            self.leftover_table.setItem(r, 2, QTableWidgetItem(item["path"]))
            if item["type"] == "folder":
                size_str = self._fmt(item.get("size", 0))
                total_leftover_size += item.get("size", 0)
            else:
                size_str = "-"
            self.leftover_table.setItem(r, 3, QTableWidgetItem(size_str))

        cleaned = leftover_results.get("deleted", 0)
        freed = leftover_results.get("freed_bytes", 0)
        failed = leftover_results.get("failed", 0)

        if leftovers:
            self.log_text.append(f"T\u00ecm th\u1ea5y {len(leftovers)} m\u1ee5c s\u00f3t l\u1ea1i. \u0110\u00e3 d\u1ecdn {cleaned}, l\u1ed7i {failed}, gi\u1ea3i ph\u00f3ng {self._fmt(freed)}")
            msg = f"\u0110\u00e3 g\u1ee1: {name}\n\nD\u1eef li\u1ec7u s\u00f3t l\u1ea1i:\n  - T\u00ecm th\u1ea5y: {len(leftovers)} m\u1ee5c\n  - \u0110\u00e3 x\u00f3a: {cleaned} m\u1ee5c\n  - Gi\u1ea3i ph\u00f3ng: {self._fmt(freed)}"
            if failed:
                msg += f"\n  - L\u1ed7i: {failed} m\u1ee5c"
            if hasattr(parent, 'message_modal'):
                parent.message_modal.info("K\u1ebft qu\u1ea3 g\u1ee1 b\u1ecf", msg)
        else:
            self.log_text.append("Kh\u00f4ng t\u00ecm th\u1ea5y d\u1eef li\u1ec7u s\u00f3t l\u1ea1i.")
            if hasattr(parent, 'message_modal'):
                parent.message_modal.success("Th\u00e0nh c\u00f4ng", f"\u0110\u00e3 g\u1ee1 s\u1ea1ch: {name}")

        self.clean_btn.setEnabled(bool(leftovers))
        self.uninstall_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)

    def _scan_leftovers(self):
        row = self.table.currentRow()
        if row < 0:
            return
        name = self.table.item(row, 0).text()
        prog = next((p for p in self._programs if p["name"] == name), None)
        if not prog:
            return
        self.log_text.append(f"\u0110ang qu\u00e9t leftover cho: {name}...")
        worker = ScanLeftoverWorker(prog)
        worker.finished.connect(self._on_scan_leftover_done)
        worker.start()

    def _on_scan_leftover_done(self, leftovers):
        self._leftovers = leftovers
        self.leftover_table.setRowCount(len(leftovers))
        total_size = 0
        for r, item in enumerate(leftovers):
            self.leftover_table.setItem(r, 0, QTableWidgetItem(item["type"]))
            self.leftover_table.setItem(r, 1, QTableWidgetItem(item["source"]))
            self.leftover_table.setItem(r, 2, QTableWidgetItem(item["path"]))
            if item["type"] == "folder":
                size_str = self._fmt(item.get("size", 0))
                total_size += item.get("size", 0)
            else:
                size_str = "-"
            self.leftover_table.setItem(r, 3, QTableWidgetItem(size_str))
        self.status_label.setText(f"T\u00ecm th\u1ea5y {len(leftovers)} m\u1ee5c leftover. T\u1ed5ng: {self._fmt(total_size)}")
        self.log_text.append(f"T\u00ecm th\u1ea5y {len(leftovers)} m\u1ee5c s\u00f3t l\u1ea1i.")
        self.clean_btn.setEnabled(bool(leftovers))

    def _clean_leftovers(self):
        if not self._leftovers:
            return
        name = self._pending_name if hasattr(self, '_pending_name') else ""
        parent = self.window()
        if hasattr(parent, 'message_modal'):
            parent.message_modal.confirm(
                "X\u00e1c nh\u1eadn x\u00f3a leftover",
                f"X\u00f3a {len(self._leftovers)} m\u1ee5c d\u1eef li\u1ec7u s\u00f3t l\u1ea1i?\n\nThao t\u00e1c n\u00e0y kh\u00f4ng th\u1ec3 ho\u00e0n t\u00e1c!",
                on_yes=self._do_clean_leftovers,
                yes_text="X\u00f3a t\u1ea5t c\u1ea3",
            )

    def _do_clean_leftovers(self):
        leftovers = self._leftovers
        if not leftovers:
            return
        self.clean_btn.setEnabled(False)
        self.log_text.append(f"\u0110ang x\u00f3a {len(leftovers)} m\u1ee5c leftover...")
        result = tools.clean_all_leftovers("", leftovers)
        self.log_text.append(f"\u0110\u00e3 x\u00f3a: {result['deleted']}, l\u1ed7i: {result['failed']}, gi\u1ea3i ph\u00f3ng: {self._fmt(result['freed_bytes'])}")
        self.leftover_table.setRowCount(0)
        self._leftovers = []
        self.clean_btn.setEnabled(False)
        parent = self.window()
        if hasattr(parent, 'message_modal'):
            if result["failed"] == 0:
                parent.message_modal.success("D\u1ecdn s\u1ea1ch", f"\u0110\u00e3 x\u00f3a {result['deleted']} m\u1ee5c leftover, gi\u1ea3i ph\u00f3ng {self._fmt(result['freed_bytes'])}.")
            else:
                parent.message_modal.warning("D\u1ecdn leftover", f"\u0110\u00e3 x\u00f3a {result['deleted']}, l\u1ed7i {result['failed']} m\u1ee5c.")

    def _fmt(self, b: int) -> str:
        for u in ["B", "KB", "MB", "GB"]:
            if b < 1024:
                return f"{b:.1f} {u}"
            b /= 1024
        return f"{b:.1f} TB"


# --------------------------------------------------------------------------- #
# Orphaned AppData Panel - Xóa AppData còn sót từ phần mềm đã gỡ
# --------------------------------------------------------------------------- #

class OrphanedAppDataPanel(ToolPanel):
    def __init__(self, parent=None):
        super().__init__("AppData s\u00f3t", "Qu\u00e9t v\u00e0 x\u00f3a th\u01b0 m\u1ee5c AppData/ProgramData c\u00f2n s\u00f3t t\u1eeb ph\u1ea7n m\u1ec1m \u0111\u00e3 g\u1ee1, gi\u1ea3i ph\u00f3ng dung l\u01b0\u1ee3ng \u1ed5 C:.", "trash", parent)
        self._orphans = []

        btn_row = QHBoxLayout()
        self.scan_btn = _icon_btn("Qu\u00e9t AppData s\u00f3t", "search", "PrimaryButton")
        self.scan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self.scan_btn)

        self.delete_btn = _icon_btn("X\u00f3a \u0111\u00e3 ch\u1ecdn", "trash", "DangerButton")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.delete_btn)

        self.delete_all_btn = _icon_btn("X\u00f3a t\u1ea5t c\u1ea3", "trash", "DangerButton")
        self.delete_all_btn.setEnabled(False)
        self.delete_all_btn.clicked.connect(self._delete_all)
        btn_row.addWidget(self.delete_all_btn)
        btn_row.addStretch(1)
        self.content_layout.addLayout(btn_row)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["", "Th\u01b0 m\u1ee5c", "V\u1ecb tr\u00ed", "\u0110\u01b0\u1eddng d\u1eabn", "S\u1ed1 file", "Dung l\u01b0\u1ee3ng"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.MultiSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setObjectName("ToolTable")
        self.table.itemSelectionChanged.connect(self._on_sel)
        self.content_layout.addWidget(self.table, 1)

        self.total_label = QLabel("T\u1ed5ng: 0 B")
        self.total_label.setObjectName("ToolTotalLabel")
        self.total_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 6px 0;")
        self.content_layout.addWidget(self.total_label)

        self.progress = QProgressBar()
        self.progress.setObjectName("ScanProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.content_layout.addWidget(self.progress)

        self.status_label = QLabel("Nh\u1ea5n \"Qu\u00e9t\" \u0111\u1ec3 t\u00ecm th\u01b0 m\u1ee5c AppData c\u00f2n s\u00f3t.")
        self.status_label.setObjectName("ToolStatusLabel")
        self.content_layout.addWidget(self.status_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("ToolOutput")
        self.log_text.setMaximumHeight(120)
        self.log_text.setPlaceholderText("Nh\u1eadt k\u00fd d\u1ecdn AppData...")
        self.content_layout.addWidget(self.log_text)

    def _start_scan(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(f"\u0110ang qu\u00e9t...")
        self.delete_btn.setEnabled(False)
        self.delete_all_btn.setEnabled(False)
        self.table.setRowCount(0)
        self.log_text.clear()
        self.log_text.append("\u0110ang qu\u00e9t AppData/ProgramData t\u00ecm th\u01b0 m\u1ee5c s\u00f3t...")
        self._worker = OrphanedAppDataWorker()
        self._worker.finished.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self, orphans):
        self._orphans = orphans
        self.table.setRowCount(len(orphans))
        total_size = 0
        for r, o in enumerate(orphans):
            open_btn = QPushButton("\uD83D\uDCC2")
            open_btn.setFixedSize(28, 28)
            open_btn.setToolTip("M\u1edf v\u1ecb tr\u00ed th\u01b0 m\u1ee5c")
            open_btn.setCursor(Qt.PointingHandCursor)
            open_btn.clicked.connect(lambda checked, p=o["path"]: os.startfile(p))
            self.table.setCellWidget(r, 0, open_btn)
            self.table.setItem(r, 1, QTableWidgetItem(o["name"]))
            self.table.setItem(r, 2, QTableWidgetItem(o["source"]))
            self.table.setItem(r, 3, QTableWidgetItem(o["path"]))
            self.table.setItem(r, 4, QTableWidgetItem(str(o["file_count"])))
            size_str = self._fmt(o["size_bytes"])
            self.table.setItem(r, 5, QTableWidgetItem(size_str))
            total_size += o["size_bytes"]
            self.log_text.append(f"  {o['name']}: {size_str} ({o['source']})")

        self.scan_btn.setEnabled(True)
        self.scan_btn.setText(f"Qu\u00e9t AppData s\u00f3t")
        self.total_label.setText(f"T\u1ed5ng: {self._fmt(total_size)} ({len(orphans)} th\u01b0 m\u1ee5c)")
        self.status_label.setText(f"T\u00ecm th\u1ea5y {len(orphans)} th\u01b0 m\u1ee5c s\u00f3t, t\u1ed5ng {self._fmt(total_size)}.")
        self.log_text.append(f"Ho\u00e0n t\u1ea5t. T\u00ecm th\u1ea5y {len(orphans)} th\u01b0 m\u1ee5c AppData s\u00f3t, t\u1ed5ng {self._fmt(total_size)}.")
        self.delete_all_btn.setEnabled(bool(orphans))

    def _on_sel(self):
        self.delete_btn.setEnabled(bool(self.table.selectedItems()))

    def _delete_selected(self):
        rows = set()
        for item in self.table.selectedItems():
            rows.add(item.row())
        if not rows:
            return
        to_delete = [self._orphans[r] for r in sorted(rows) if r < len(self._orphans)]
        total = self._fmt(sum(o["size_bytes"] for o in to_delete))
        parent = self.window()
        if hasattr(parent, 'message_modal'):
            parent.message_modal.danger_confirm(
                "C\u1ea3nh b\u00e1o nguy hi\u1ec3m",
                f"D\u1eef li\u1ec7u s\u1ebd b\u1ecb x\u00f3a V\u0128NH VI\u1ec4N, kh\u00f4ng th\u1ec3 kh\u00f4i ph\u1ee5c!\n\n"
                f"X\u00f3a {len(to_delete)} th\u01b0 m\u1ee5c \u0111\u00e3 ch\u1ecdn.\n"
                f"Dung l\u01b0\u1ee3ng: {total}\n\n"
                f"H\u00e3y ch\u1eafc ch\u1eafn \u0111\u00e2y l\u00e0 d\u1eef li\u1ec7u t\u1eeb ph\u1ea7n m\u1ec1m \u0111\u00e3 g\u1ee1.",
                on_yes=lambda: self._start_delete(to_delete),
                yes_text="X\u00f3a \u0111\u00e3 ch\u1ecdn",
            )

    def _delete_all(self):
        if not self._orphans:
            return
        parent = self.window()
        total = self._fmt(sum(o["size_bytes"] for o in self._orphans))
        if hasattr(parent, 'message_modal'):
            parent.message_modal.danger_confirm(
                "C\u1ea3nh b\u00e1o nguy hi\u1ec3m",
                f"D\u1eef li\u1ec7u s\u1ebd b\u1ecb x\u00f3a V\u0128NH VI\u1ec4N, kh\u00f4ng th\u1ec3 kh\u00f4i ph\u1ee5c!\n\n"
                f"X\u00f3a {len(self._orphans)} th\u01b0 m\u1ee5c AppData s\u00f3t.\n"
                f"T\u1ed5ng dung l\u01b0\u1ee3ng: {total}\n\n"
                f"H\u00e3y ch\u1eafc ch\u1eafn \u0111\u00e2y l\u00e0 d\u1eef li\u1ec7u t\u1eeb ph\u1ea7n m\u1ec1m \u0111\u00e3 g\u1ee1.",
                on_yes=lambda: self._start_delete(self._orphans),
                yes_text="T\u00f4i hi\u1ec3u, x\u00f3a t\u1ea5t c\u1ea3",
            )

    def _start_delete(self, items):
        if not items:
            return
        self.delete_btn.setEnabled(False)
        self.delete_all_btn.setEnabled(False)
        self.scan_btn.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()

        self._delete_worker = OrphanedDeleteWorker(items)
        self._delete_worker.progress.connect(self._on_delete_progress)
        self._delete_worker.finished.connect(self._on_delete_done)
        self._delete_worker.start()

    def _on_delete_progress(self, current, total, path):
        pct = int(current / total * 100)
        self.progress.setValue(pct)
        self.status_label.setText(f"\u0110ang x\u00f3a ({current}/{total}): {os.path.basename(path)}")
        self.log_text.append(f"\u0110ang x\u00f3a: {path}...")

    def _on_delete_done(self, deleted, freed, failed):
        self.progress.setValue(100)
        self.progress.hide()
        self.total_label.setText(f"\u0110\u00e3 gi\u1ea3i ph\u00f3ng: {self._fmt(freed)}")
        if failed:
            self.status_label.setText(f"\u0110\u00e3 x\u00f3a {deleted}, b\u1ecf qua {len(failed)} m\u1ee5c kh\u00f4ng x\u00f3a \u0111\u01b0\u1ee3c, gi\u1ea3i ph\u00f3ng {self._fmt(freed)}")
            self.log_text.append(f"B\u1ecf qua {len(failed)} m\u1ee5c kh\u00f4ng x\u00f3a \u0111\u01b0\u1ee3c:")
            for item in failed:
                self.log_text.append(f"  - {item['name']}: {item['path']}")
            self._orphans = failed
            self.table.setRowCount(len(failed))
            for r, o in enumerate(failed):
                open_btn = QPushButton("\uD83D\uDCC2")
                open_btn.setFixedSize(28, 28)
                open_btn.setToolTip("M\u1edf v\u1ecb tr\u00ed th\u01b0 m\u1ee5c")
                open_btn.setCursor(Qt.PointingHandCursor)
                open_btn.clicked.connect(lambda checked, p=o["path"]: os.startfile(p))
                self.table.setCellWidget(r, 0, open_btn)
                self.table.setItem(r, 1, QTableWidgetItem(o["name"]))
                self.table.setItem(r, 2, QTableWidgetItem(o["source"]))
                self.table.setItem(r, 3, QTableWidgetItem(o["path"]))
                self.table.setItem(r, 4, QTableWidgetItem(str(o.get("file_count", 0))))
                self.table.setItem(r, 5, QTableWidgetItem(self._fmt(o.get("size_bytes", 0))))
                self.log_text.append(f"  {o['name']}: {o['path']}")
            self.delete_all_btn.setEnabled(bool(failed))
        else:
            self.status_label.setText(f"\u0110\u00e3 x\u00f3a {deleted} m\u1ee5c, gi\u1ea3i ph\u00f3ng {self._fmt(freed)}")
            self.log_text.append(f"Ho\u00e0n t\u1ea5t: x\u00f3a {deleted} m\u1ee5c, gi\u1ea3i ph\u00f3ng {self._fmt(freed)}")
            self._orphans = []
            self.table.setRowCount(0)
            self.delete_all_btn.setEnabled(False)
        self.log_text.append(f"Ho\u00e0n t\u1ea5t: x\u00f3a {deleted} m\u1ee5c, gi\u1ea3i ph\u00f3ng {self._fmt(freed)}")
        self.scan_btn.setEnabled(True)
        self.delete_btn.setEnabled(False)

    def _fmt(self, b: int) -> str:
        for u in ["B", "KB", "MB", "GB"]:
            if b < 1024:
                return f"{b:.1f} {u}"
            b /= 1024
        return f"{b:.1f} TB"


# --------------------------------------------------------------------------- #
# Delete Stubborn Panel
# --------------------------------------------------------------------------- #

class DeleteStubbornPanel(ToolPanel):
    def __init__(self, parent=None):
        super().__init__("X\u00f3a file/c\u01b0\u1eddng \u0111\u1ea7u", "X\u00f3a file/th\u01b0 m\u1ee5c b\u1ecb kh\u00f3a, kh\u00f4ng th\u1ec3 x\u00f3a b\u00ecnh th\u01b0\u1eddng.", "trash", parent)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Nh\u1eadp \u0111\u01b0\u1eddng d\u1eabn file/th\u01b0 m\u1ee5c c\u1ea7n x\u00f3a...")
        self.path_edit.setObjectName("ToolSearch")
        path_row.addWidget(self.path_edit, 1)

        browse_btn = QPushButton(f"{ICONS['folder']} Duy\u1ec7t...")
        browse_btn.setObjectName("SecondaryButton")
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        self.content_layout.addLayout(path_row)

        warn = QFrame()
        warn.setObjectName("ToolWarning")
        wl = QHBoxLayout(warn)
        wl.setContentsMargins(12, 8, 12, 8)
        wl.addWidget(icon_label("warning", 16, "#d29922"))
        wt = QLabel("C\u1ea3nh b\u00e1o: Thao t\u00e1c n\u00e0y kh\u00f4ng th\u1ec3 ho\u00e0n t\u00e1c. H\u00e3y ch\u1eafc ch\u1eafn \u0111\u01b0\u1eddng d\u1eabn \u0111\u00fang.")
        wt.setObjectName("ToolWarningText")
        wt.setWordWrap(True)
        wl.addWidget(wt, 1)
        self.content_layout.addWidget(warn)

        btn_row = QHBoxLayout()
        self.delete_btn = QPushButton(f"{ICONS['trash']} X\u00f3a c\u01b0\u1eddng \u0111\u1ea7u")
        self.delete_btn.setObjectName("DangerButton")
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._force_delete)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch(1)
        self.content_layout.addLayout(btn_row)

        self.result_label = QLabel("")
        self.result_label.setObjectName("ToolResultLabel")
        self.result_label.hide()
        self.content_layout.addWidget(self.result_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("ToolOutput")
        self.log_text.setMaximumHeight(160)
        self.log_text.setPlaceholderText("Nhat ky hoat dong...")
        self.content_layout.addWidget(self.log_text)

        self.path_edit.textChanged.connect(lambda t: self.delete_btn.setEnabled(bool(t.strip())))

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Ch\u1ecdn th\u01b0 m\u1ee5c c\u1ea7n x\u00f3a")
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Ch\u1ecdn file c\u1ea7n x\u00f3a")
        if path:
            self.path_edit.setText(path)

    def _force_delete(self):
        path = self.path_edit.text().strip()
        if not path:
            return
        if not os.path.exists(path):
            parent = self.window()
            if hasattr(parent, 'message_modal'):
                parent.message_modal.error("L\u1ed7i", "\u0110\u01b0\u1eddng d\u1eabn kh\u00f4ng t\u1ed3n t\u1ea1i!")
            return

        self._pending_path = path
        parent = self.window()
        if hasattr(parent, 'message_modal'):
            parent.message_modal.confirm(
                "X\u00e1c nh\u1eadn x\u00f3a",
                f"B\u1ea1n c\u00f3 ch\u1eafc mu\u1ed1n x\u00f3a c\u01b0\u1eddng \u0111\u1ea7u:\n{path}\n\nThao t\u00e1c n\u00e0y KH\u00d4NG TH\u1ec2 ho\u00e0n t\u00e1c!",
                on_yes=self._do_delete,
            )
        else:
            self._do_delete()

    def _do_delete(self):
        path = getattr(self, '_pending_path', '')
        if not path:
            return
        self.delete_btn.setEnabled(False)
        self.delete_btn.setText(f"{ICONS['trash']} \u0110ang x\u00f3a...")
        self.log_text.append(f"\u0110ang x\u00f3a: {path}...")

        result = tools.force_delete(path)
        parent = self.window()

        if result.get("success"):
            msg = f"{ICONS['check']} {result.get('output', '\u0110\u00e3 x\u00f3a th\u00e0nh c\u00f4ng.')}"
            self.result_label.setText(msg)
            self.log_text.append(msg)
            self.path_edit.clear()
            if hasattr(parent, 'message_modal'):
                parent.message_modal.success("Th\u00e0nh c\u00f4ng", result.get('output', '\u0110\u00e3 x\u00f3a.'))
        else:
            msg = f"{ICONS['x']} {result.get('error', 'L\u1ed7i.')}"
            self.result_label.setText(msg)
            self.log_text.append(msg)
            if hasattr(parent, 'message_modal'):
                parent.message_modal.error("L\u1ed7i", result.get('error', 'Kh\u00f4ng th\u1ec3 x\u00f3a.'))

        self.result_label.show()
        self.delete_btn.setEnabled(True)
        self.delete_btn.setText(f"{ICONS['trash']} X\u00f3a c\u01b0\u1eddng \u0111\u1ea7u")


# --------------------------------------------------------------------------- #
# Virus Scanner Panel
# --------------------------------------------------------------------------- #

class VirusScannerPanel(ToolPanel):
    def __init__(self, parent=None):
        super().__init__("Qu\u00e9t di\u1ec7t virus", "Ki\u1ec3m tra h\u1ec7 th\u1ed1ng b\u1eb1ng Windows Defender.", "shield", parent)

        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton(f"{ICONS['search']} Qu\u00e9t m\u1edbi \u0111\u00e9 d\u1ecda")
        self.scan_btn.setObjectName("PrimaryButton")
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self.scan_btn)

        self.status_btn = QPushButton(f"{ICONS['info']} Tr\u1ea1ng th\u00e1i Defender")
        self.status_btn.setObjectName("SecondaryButton")
        self.status_btn.setCursor(Qt.PointingHandCursor)
        self.status_btn.clicked.connect(self._check_status)
        btn_row.addWidget(self.status_btn)
        btn_row.addStretch(1)
        self.content_layout.addLayout(btn_row)

        self.status_label = QLabel("Nh\u1ea5n \"Qu\u00e9t\" \u0111\u1ec3 b\u1eaft \u0111\u1ea7u.")
        self.status_label.setObjectName("ToolStatusLabel")
        self.content_layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setObjectName("ScanProgress")
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.content_layout.addWidget(self.progress)

        self.status_frame = QFrame()
        self.status_frame.setObjectName("ToolStatusFrame")
        self.status_frame.hide()
        sl = QVBoxLayout(self.status_frame)
        sl.setContentsMargins(12, 10, 12, 10)
        sl.setSpacing(4)
        self.defender_title = QLabel("Trang thai Windows Defender")
        self.defender_title.setObjectName("ToolStatusTitle")
        self.realtime_label = QLabel("")
        self.realtime_label.setObjectName("ToolStatusLabel")
        self.antivirus_label = QLabel("")
        self.antivirus_label.setObjectName("ToolStatusLabel")
        self.quick_scan_label = QLabel("")
        self.quick_scan_label.setObjectName("ToolStatusLabel")
        self.full_scan_label = QLabel("")
        self.full_scan_label.setObjectName("ToolStatusLabel")
        sl.addWidget(self.defender_title)
        sl.addWidget(self.realtime_label)
        sl.addWidget(self.antivirus_label)
        sl.addWidget(self.quick_scan_label)
        sl.addWidget(self.full_scan_label)
        self.content_layout.addWidget(self.status_frame)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Moi de doa", "Thoi gian", "Hanh dong", "Tai nguyen"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setObjectName("ToolTable")
        self.content_layout.addWidget(self.table, 1)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("ToolOutput")
        self.log_text.setMaximumHeight(100)
        self.log_text.setPlaceholderText("Nhat ky quet...")
        self.content_layout.addWidget(self.log_text)

    def _start_scan(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(f"{ICONS['search']} \u0110ang qu\u00e9t...")
        self.progress.show()
        self.table.setRowCount(0)
        self.status_label.setText("\u0110ang qu\u00e9t h\u1ec7 th\u1ed1ng...")
        self.log_text.append("B\u1eaft \u0111\u1ea7u qu\u00e9t m\u1edbi \u0111\u00e9 d\u1ecda...")
        self._worker = VirusScanWorker()
        self._worker.finished.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self, result):
        self.progress.hide()
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText(f"{ICONS['search']} Qu\u00e9t m\u1edbi \u0111\u00e9 d\u1ecda")
        threats = result.get("threats", [])
        self.status_label.setText(result.get("message", "Qu\u00e9t xong."))
        self.log_text.append(result.get("message", "Qu\u00e9t xong."))

        if threats:
            self.table.setRowCount(len(threats))
            for r, t in enumerate(threats):
                self.table.setItem(r, 0, QTableWidgetItem(t.get("ThreatName", "N/A")))
                self.table.setItem(r, 1, QTableWidgetItem(str(t.get("DetectionTime", ""))))
                self.table.setItem(r, 2, QTableWidgetItem(str(t.get("ActionSuccess", ""))))
                self.table.setItem(r, 3, QTableWidgetItem(str(t.get("Resources", ""))))
        else:
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem("Kh\u00f4ng ph\u00e1t hi\u1ec7n m\u1edbi \u0111\u00e9 d\u1ecda"))
            self.table.setSpan(0, 0, 1, 4)

    def _check_status(self):
        status = tools.get_defender_status()
        if "error" in status:
            self.status_label.setText(status["error"])
            return
        rt = status.get('realtime', False)
        en = status.get('enabled', False)
        self.realtime_label.setText(f"B\u1ea3o v\u1ec7 th\u1eddi gian th\u1ef1c: {ICONS['check'] if rt else ICONS['x']} {'B\u1eadt' if rt else 'T\u1eaft'}")
        self.antivirus_label.setText(f"Antivirus: {ICONS['check'] if en else ICONS['x']} {'B\u1eadt' if en else 'T\u1eaft'}")

        from datetime import datetime
        qs = status.get("quick_scan", "")
        if qs:
            try:
                qs = datetime.fromisoformat(qs.replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
            except Exception:
                pass
        self.quick_scan_label.setText(f"Qu\u00e9t nhanh l\u1ea7n cu\u1ed1i: {qs or 'Ch\u01b0a c\u00f3'}")

        fs = status.get("full_scan", "")
        if fs:
            try:
                fs = datetime.fromisoformat(fs.replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
            except Exception:
                pass
        self.full_scan_label.setText(f"Qu\u00e9t to\u00e0n b\u1ed9 l\u1ea7n cu\u1ed1i: {fs or 'Ch\u01b0a c\u00f3'}")
        self.status_frame.show()
        self.log_text.append("\u0110\u00e3 t\u1ea3i tr\u1ea1ng th\u00e1i Defender.")


# --------------------------------------------------------------------------- #
# Memory Card Recovery Panel
# --------------------------------------------------------------------------- #

class MemoryCardRecoveryPanel(ToolPanel):
    def __init__(self, parent=None):
        super().__init__("Ph\u1ee5c h\u1ed3i th\u1ebb nh\u1edd", "Qu\u00e9t v\u00e0 ph\u1ee5c h\u1ed3i file \u0111\u00e3 x\u00f3a tr\u00ean th\u1ebb nh\u1edd/USB.", "sdcard", parent)
        self._drives = []

        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton(f"{ICONS['refresh']} Ph\u00e1t hi\u1ec7n \u1ed9 \u0111\u00eda")
        self.scan_btn.setObjectName("PrimaryButton")
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.clicked.connect(self._scan_drives)
        btn_row.addWidget(self.scan_btn)

        self.recover_btn = QPushButton(f"{ICONS['arrow_r']} Qu\u00e9t ph\u1ee5c h\u1ed3i")
        self.recover_btn.setObjectName("AccentButton")
        self.recover_btn.setCursor(Qt.PointingHandCursor)
        self.recover_btn.setEnabled(False)
        self.recover_btn.clicked.connect(self._recover)
        btn_row.addWidget(self.recover_btn)
        btn_row.addStretch(1)
        self.content_layout.addLayout(btn_row)

        self.status_label = QLabel("Nh\u1ea5n \"Ph\u00e1t hi\u1ec7n \u1ed9 \u0111\u00eda\" \u0111\u1ec3 t\u00ecm th\u1ebb nh\u1edd/USB.")
        self.status_label.setObjectName("ToolStatusLabel")
        self.content_layout.addWidget(self.status_label)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["K\u00fd hi\u1ec7u", "Nh\u00e3n", "File system", "Dung l\u01b0\u1ee3ng", "S\u1ee9c kh\u1ecfe"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setObjectName("ToolTable")
        self.table.itemSelectionChanged.connect(self._on_sel)
        self.content_layout.addWidget(self.table, 1)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("ToolOutput")
        self.log_text.setMaximumHeight(140)
        self.log_text.setPlaceholderText("Nh\u1eadt k\u00fd ph\u1ee5c h\u1ed3i...")
        self.content_layout.addWidget(self.log_text)

    def _scan_drives(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(f"{ICONS['refresh']} \u0110ang qu\u00e9t...")
        self.table.setRowCount(0)
        self.log_text.append("\u0110ang ph\u00e1t hi\u1ec7n \u1ed9 \u0111\u00eda \u0111\u1ed9ng...")
        self._worker = DriveScanWorker()
        self._worker.finished.connect(self._on_drives)
        self._worker.start()

    def _on_drives(self, drives):
        self._drives = drives
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText(f"{ICONS['refresh']} Ph\u00e1t hi\u1ec7n \u1ed9 \u0111\u00eda")

        if not drives:
            self.status_label.setText("Kh\u00f4ng t\u00ecm th\u1ea5y \u1ed9 \u0111\u00eda \u0111\u1ed9ng (USB/th\u1ebb nh\u1edd).")
            self.log_text.append("Kh\u00f4ng t\u00ecm th\u1ea5y th\u1ebb nh\u1edd/USB.")
            return

        self.table.setRowCount(len(drives))
        for r, d in enumerate(drives):
            self.table.setItem(r, 0, QTableWidgetItem(f"{d['letter']}:"))
            self.table.setItem(r, 1, QTableWidgetItem(d.get("label", "")))
            self.table.setItem(r, 2, QTableWidgetItem(d.get("filesystem", "")))
            total = d.get("total_bytes", 0)
            s = f"{total/1073741824:.1f} GB" if total > 1073741824 else f"{total/1048576:.0f} MB"
            self.table.setItem(r, 3, QTableWidgetItem(s))
            self.table.setItem(r, 4, QTableWidgetItem(d.get("health", "Unknown")))
            self.log_text.append(f"  T\u00ecm th\u1ea5y: {d['letter']}: {d.get('label', '')} ({s})")

        self.status_label.setText(f"T\u00ecm th\u1ea5y {len(drives)} \u1ed9 \u0111\u00eda \u0111\u1ed9ng.")
        self.log_text.append(f"Ph\u00e1t hi\u1ec7n xong: {len(drives)} \u1ed9 \u0111\u00eda.")

    def _on_sel(self):
        self.recover_btn.setEnabled(bool(self.table.selectedItems()))

    def _recover(self):
        row = self.table.currentRow()
        if row < 0:
            return
        drive = self._drives[row]
        path = drive["path"]
        self.log_text.append(f"\u0110ang qu\u00e9t ph\u1ee5c h\u1ed3i tr\u00ean {drive['letter']}:...")

        result = tools.recover_deleted_files(path)
        count = result.get("count", 0)
        self.log_text.append(f"T\u00ecm th\u1ea5y {count} file \u1ea9n/\u0111\u00e3 x\u00f3a.")

        parent = self.window()
        if hasattr(parent, 'message_modal'):
            parent.message_modal.info(
                "K\u1ebft qu\u1ea3 qu\u00e9t",
                f"T\u00ecm th\u1ea5y {count} file \u1ea9n/\u0111\u00e3 x\u00f3a tr\u00ean \u1ed9 {drive['letter']}:\n\n"
                + "\n".join([f"  - {f.get('FullName', '')}" for f in result.get('hidden_files', [])[:10]])
                + ("\n..." if count > 10 else ""),
            )
        else:
            self.status_label.setText(f"T\u00ecm th\u1ea5y {count} file \u1ea9n.")


# --------------------------------------------------------------------------- #
# Memory Card Repair Panel
# --------------------------------------------------------------------------- #

class MemoryCardRepairPanel(ToolPanel):
    def __init__(self, parent=None):
        super().__init__("S\u1eefa ch\u1ee9a th\u1ebb nh\u1edd", "Ch\u1ed9ng l\u1ed7i th\u1ebb nh\u1edd/USB: RAW, read-only, format l\u1ed7i, bad sectors.", "sdcard", parent)
        self._drives = []
        self._diag = {}

        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton(f"{ICONS['refresh']} Qu\u00e9t th\u1ebb nh\u1edd")
        self.scan_btn.setObjectName("PrimaryButton")
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.clicked.connect(self._scan_drives)
        btn_row.addWidget(self.scan_btn)

        self.diag_btn = QPushButton(f"{ICONS['search']} Ch\u1ee9ng \u0111\u00f3nh")
        self.diag_btn.setObjectName("SecondaryButton")
        self.diag_btn.setCursor(Qt.PointingHandCursor)
        self.diag_btn.setEnabled(False)
        self.diag_btn.clicked.connect(self._diagnose)
        btn_row.addWidget(self.diag_btn)

        self.fix_ro_btn = QPushButton(f"{ICONS['settings']} T\u1eaft Read-Only")
        self.fix_ro_btn.setObjectName("SecondaryButton")
        self.fix_ro_btn.setCursor(Qt.PointingHandCursor)
        self.fix_ro_btn.setEnabled(False)
        self.fix_ro_btn.clicked.connect(self._fix_readonly)
        btn_row.addWidget(self.fix_ro_btn)

        self.repair_btn = QPushButton(f"{ICONS['settings']} S\u1eefa ch\u1ee9a FS")
        self.repair_btn.setObjectName("AccentButton")
        self.repair_btn.setCursor(Qt.PointingHandCursor)
        self.repair_btn.setEnabled(False)
        self.repair_btn.clicked.connect(self._repair)
        btn_row.addWidget(self.repair_btn)

        self.format_btn = QPushButton(f"{ICONS['trash']} Format an to\u00e0n")
        self.format_btn.setObjectName("DangerButton")
        self.format_btn.setCursor(Qt.PointingHandCursor)
        self.format_btn.setEnabled(False)
        self.format_btn.clicked.connect(self._safe_format)
        btn_row.addWidget(self.format_btn)

        self.force_format_btn = QPushButton(f"{ICONS['x']} Format b\u1eaft bu\u1ed9c")
        self.force_format_btn.setObjectName("DangerButton")
        self.force_format_btn.setCursor(Qt.PointingHandCursor)
        self.force_format_btn.setEnabled(False)
        self.force_format_btn.clicked.connect(self._force_format)
        btn_row.addWidget(self.force_format_btn)
        btn_row.addStretch(1)
        self.content_layout.addLayout(btn_row)

        fs_row = QHBoxLayout()
        fs_row.setSpacing(8)
        fs_label = QLabel("D\u1ea1ng format:")
        fs_label.setObjectName("ToolStatusLabel")
        self.fs_combo = QComboBox()
        self.fs_combo.addItems(["exFAT", "FAT32", "NTFS"])
        self.fs_combo.setObjectName("ToolSearch")
        self.fs_combo.setMinimumWidth(100)
        self.fs_combo.currentTextChanged.connect(self._on_fs_changed)
        fs_row.addWidget(fs_label)
        fs_row.addWidget(self.fs_combo)
        fs_row.addStretch(1)
        self.content_layout.addLayout(fs_row)

        self.status_label = QLabel("Ch\u1ecdn \u1ed9 \u0111\u00eda th\u1ebb nh\u1edd \u0111\u1ec3 b\u1eaft \u0111\u1ea7u.")
        self.status_label.setObjectName("ToolStatusLabel")
        self.content_layout.addWidget(self.status_label)

        self.diag_frame = QFrame()
        self.diag_frame.setObjectName("ToolStatusFrame")
        self.diag_frame.hide()
        dl = QVBoxLayout(self.diag_frame)
        dl.setContentsMargins(12, 10, 12, 10)
        dl.setSpacing(4)
        self.diag_title = QLabel("K\u1ebft qu\u1ea3 ch\u1ee9ng \u0111\u00f3nh")
        self.diag_title.setObjectName("ToolStatusTitle")
        self.diag_fs = QLabel("")
        self.diag_fs.setObjectName("ToolStatusLabel")
        self.diag_health = QLabel("")
        self.diag_health.setObjectName("ToolStatusLabel")
        self.diag_issues = QLabel("")
        self.diag_issues.setObjectName("ToolStatusLabel")
        self.diag_issues.setWordWrap(True)
        self.diag_rec = QLabel("")
        self.diag_rec.setObjectName("ToolStatusLabel")
        self.diag_rec.setWordWrap(True)
        dl.addWidget(self.diag_title)
        dl.addWidget(self.diag_fs)
        dl.addWidget(self.diag_health)
        dl.addWidget(self.diag_issues)
        dl.addWidget(self.diag_rec)
        self.content_layout.addWidget(self.diag_frame)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["K\u00fd hi\u1ec7u", "Nh\u00e3n", "File system", "Dung l\u01b0\u1ee3ng", "S\u1ee9c kh\u1ecfe"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setObjectName("ToolTable")
        self.table.itemSelectionChanged.connect(self._on_sel)
        self.content_layout.addWidget(self.table, 1)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("ToolOutput")
        self.log_text.setMaximumHeight(140)
        self.log_text.setPlaceholderText("Nh\u1eadt k\u00fd s\u1eefa ch\u1ee9a...")
        self.content_layout.addWidget(self.log_text)

    def _scan_drives(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(f"{ICONS['refresh']} \u0110ang qu\u00e9t...")
        self.table.setRowCount(0)
        self.diag_frame.hide()
        self.log_text.append("\u0110ang qu\u00e9t th\u1ebb nh\u1edd...")
        self._worker = DriveScanWorker()
        self._worker.finished.connect(self._on_drives)
        self._worker.start()

    def _on_drives(self, drives):
        self._drives = drives
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText(f"{ICONS['refresh']} Qu\u00e9t th\u1ebb nh\u1edd")

        if not drives:
            self.status_label.setText("Kh\u00f4ng t\u00ecm th\u1ea5y th\u1ebb nh\u1edd/USB.")
            self.log_text.append("Kh\u00f4ng t\u00ecm th\u1ea5y th\u1ebb nh\u1edd.")
            return

        self.table.setRowCount(len(drives))
        for r, d in enumerate(drives):
            self.table.setItem(r, 0, QTableWidgetItem(f"{d['letter']}:"))
            self.table.setItem(r, 1, QTableWidgetItem(d.get("label", "")))
            self.table.setItem(r, 2, QTableWidgetItem(d.get("filesystem", "")))
            total = d.get("total_bytes", 0)
            s = f"{total/1073741824:.1f} GB" if total > 1073741824 else f"{total/1048576:.0f} MB"
            self.table.setItem(r, 3, QTableWidgetItem(s))
            self.table.setItem(r, 4, QTableWidgetItem(d.get("health", "Unknown")))

        self.status_label.setText(f"T\u00ecm th\u1ea5y {len(drives)} \u1ed9 \u0111\u00eda. Ch\u1ecdn \u1ed9 \u0111\u00eda v\u00e0 nh\u1ea5n \"Ch\u1ee9ng \u0111\u00f3nh\" \u0111\u1ec3 ki\u1ec3m tra chi ti\u1ebft.")
        self.log_text.append(f"T\u00ecm th\u1ea5y {len(drives)} th\u1ebb nh\u1edd/USB.")

    def _on_sel(self):
        has_sel = bool(self.table.selectedItems())
        self.diag_btn.setEnabled(has_sel)
        self.fix_ro_btn.setEnabled(has_sel)
        self.repair_btn.setEnabled(has_sel)
        self.format_btn.setEnabled(has_sel)
        self.force_format_btn.setEnabled(has_sel)

    def _get_selected_letter(self) -> str:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._drives):
            return ""
        return self._drives[row]["letter"]

    def _diagnose(self):
        letter = self._get_selected_letter()
        if not letter:
            return
        self.log_text.append(f"\u0110ang ch\u1ee9ng \u0111\u00f3nh \u1ed9 {letter}:...")
        result = tools.diagnose_drive(letter)
        self._diag = result

        fs = result.get("filesystem", "N/A")
        health = result.get("health", "Unknown")
        issues = result.get("issues", [])
        recs = result.get("recommendations", [])

        self.diag_fs.setText(f"File system: {fs} | Dung l\u01b0\u1ee3ng: {result.get('total_bytes', 0)/1073741824:.1f} GB")
        self.diag_health.setText(f"S\u1ee9c kh\u1ecfe: {health} | tr\u1ea1ng th\u00e1i: {'RAW' if result.get('is_raw') else 'B\u00ecnh th\u01b0\u1eddng'}")

        if result.get("is_readonly"):
            self.diag_issues.setText(f"{ICONS['warning']} V\u1ea5n \u0111\u1ec1: {', '.join(issues)}")
            self.diag_issues.setStyleSheet("color: #d29922;")
        elif result.get("is_raw"):
            self.diag_issues.setText(f"{ICONS['x']} V\u1ea5n \u0111\u1ec1: {', '.join(issues)}")
            self.diag_issues.setStyleSheet("color: #f85149;")
        elif "kh\u00f4ng ph\u00e1t hi\u1ec7n" in str(issues):
            self.diag_issues.setText(f"{ICONS['check']} {', '.join(issues)}")
            self.diag_issues.setStyleSheet("color: #3fb950;")
        else:
            self.diag_issues.setText(f"{ICONS['warning']} {', '.join(issues)}")
            self.diag_issues.setStyleSheet("color: #d29922;")

        self.diag_rec.setText("G\u1ee3i \u00fd: " + " | ".join(recs))
        self.diag_frame.show()

        self.log_text.append(f"  File system: {fs}")
        self.log_text.append(f"  S\u1ee9c kh\u1ecfe: {health}")
        for issue in issues:
            self.log_text.append(f"  {ICONS['warning']} {issue}")
        for rec in recs:
            self.log_text.append(f"  {ICONS['arrow_r']} {rec}")

        self.status_label.setText(f"\u1ed8 {letter}: {fs} - {health}")

    def _fix_readonly(self):
        letter = self._get_selected_letter()
        if not letter:
            return
        self.log_text.append(f"\u0110ang t\u1eaft read-only cho \u1ed9 {letter}:...")
        result = tools.fix_readonly(letter)
        output = result.get("output", "")
        self.log_text.append(f"  K\u1ebft qu\u1ea3: {output}")
        parent = self.window()
        if hasattr(parent, 'message_modal'):
            parent.message_modal.info("T\u1eaft Read-Only", output)
        self._diagnose()

    def _repair(self):
        letter = self._get_selected_letter()
        if not letter:
            return
        parent = self.window()
        if hasattr(parent, 'message_modal'):
            parent.message_modal.confirm(
                "X\u00e1c nh\u1eadn s\u1eefa ch\u1ee9a",
                f"B\u1ea1n c\u00f3 ch\u1eafc mu\u1ed1n s\u1eefa ch\u1ee9a file system tr\u00ean \u1ed9 {letter}:?\n\n"
                "Thao t\u00e1c n\u00e0y s\u1ebd ch\u1ea1y chkdsk /R /F v\u00e0 c\u00f3 th\u1ec3 m\u1ea5t th\u1eddi gian.\n"
                "N\u1ebfu \u1ed9 \u0111\u00eda RAW, vui l\u00f2ng d\u00f9ng \"Format an to\u00e0n\" thay v\u00ec.",
                on_yes=lambda: self._do_repair(letter),
            )
        else:
            self._do_repair(letter)

    def _do_repair(self, letter):
        self.log_text.append(f"\u0110ang s\u1eefa ch\u1ee9a \u1ed9 {letter}:...")
        result = tools.repair_filesystem(letter)
        ok = result.get("success", False)
        output = result.get("output", "")
        issues = result.get("issues", [])

        for issue in issues:
            self.log_text.append(f"  {issue}")

        self.log_text.append(f"  K\u1ebft qu\u1ea3: {'Th\u00e0nh c\u00f4ng' if ok else 'L\u1ed7i'}")
        if output:
            self.log_text.append(f"  {output[:500]}")

        parent = self.window()
        if hasattr(parent, 'message_modal'):
            if ok:
                parent.message_modal.success("S\u1eefa ch\u1ee9a xong", f"\u0110\u00e3 s\u1eefa ch\u1ee9a \u1ed9 {letter}:")
            else:
                recommendation = result.get("recommendation", "")
                msg = f"Kh\u00f4ng th\u1ec3 s\u1eefa ch\u1ee9a \u1ed9 {letter}."
                if recommendation:
                    msg += f"\n\nG\u1ee3i \u00fd: {recommendation}"
                parent.message_modal.error("L\u1ed7i", msg)
        self._diagnose()

    def _on_fs_changed(self, fs: str):
        pass

    def _safe_format(self):
        letter = self._get_selected_letter()
        if not letter:
            return
        fs = self.fs_combo.currentText()
        parent = self.window()
        if hasattr(parent, 'message_modal'):
            parent.message_modal.confirm(
                "C\u1ea3NH B\u00c1O: Format \u0111\u00eda",
                f"B\u1ea1n c\u00f3 CH\u1ea6C MU\u1ed0N format \u1ed9 {letter}: voi\u0323 {fs}?\n\n"
                "T\u1ea5t c\u1ea3 d\u1eef li\u1ec7u tr\u00ean \u1ed9 \u0111\u00eda s\u1ebd b\u1ecb X\u00d3A HO\u00c0N TO\u00c0N.\n\n"
                "Thao t\u00e1c n\u00e0y s\u1ebd:\n"
                "  1. T\u1eaft read-only n\u1ebfu c\u00f3\n"
                f"  2. Format \u1ed9 \u0111\u00eda voi\u0323 {fs}\n"
                "  3. T\u1ea1o label \"USB_DRIVE\"\n\n"
                "B\u1ea1n c\u00f3 ch\u1eafc kh\u00f4ng?",
                on_yes=lambda: self._do_format(letter, fs),
                yes_text="Format ngay",
                no_text="H\u1ee7y",
            )
        else:
            self._do_format(letter, fs)

    def _do_format(self, letter, fs="exFAT"):
        self.log_text.append(f"\u0110ang format \u1ed9 {letter}: voi\u0323 {fs}...")
        self.format_btn.setEnabled(False)
        self.format_btn.setText(f"{ICONS['trash']} \u0110ang format...")
        result = tools.safe_format(letter, fs)
        ok = result.get("success", False)
        output = result.get("output", "")
        issues = result.get("issues", [])

        for issue in issues:
            self.log_text.append(f"  {issue}")

        self.log_text.append(f"  K\u1ebft qu\u1ea3: {'Th\u00e0nh c\u00f4ng' if ok else 'L\u1ed7i'}")
        if output:
            self.log_text.append(f"  {output[:500]}")

        parent = self.window()
        if hasattr(parent, 'message_modal'):
            if ok:
                parent.message_modal.success(
                    "Format xong",
                    f"\u0110\u00e3 format th\u00e0nh c\u00f4ng \u1ed9 {letter}: voi\u0323 {fs}.\n\nB\u1ea1n c\u00f3 th\u1ec3 s\u1eed d\u1ee5ng \u0111\u01b0\u1eddng d\u1eabn {letter}:\\",
                    on_ok=lambda: self._scan_drives(),
                )
            else:
                parent.message_modal.error(
                    "L\u1ed7i format",
                    f"Kh\u00f4ng th\u1ec3 format \u1ed9 {letter}: voi\u0323 {fs}.\n\n{output[:300]}",
                )
        self.format_btn.setEnabled(True)
        self.format_btn.setText(f"{ICONS['trash']} Format an to\u00e0n")
        self._diagnose()

    def _force_format(self):
        letter = self._get_selected_letter()
        if not letter:
            return
        fs = self.fs_combo.currentText()
        parent = self.window()
        if hasattr(parent, 'message_modal'):
            parent.message_modal.confirm(
                "C\u1ea3NH B\u00c1O: Format b\u1eaft bu\u1ed9c",
                f"B\u1ea1n c\u00f3 CH\u1ea6C MU\u1ed0N format b\u1eaft bu\u1ed9c \u1ed9 {letter}: voi\u0323 {fs}?\n\n"
                "Thao t\u00e1c n\u00e0y s\u1ebd:\n"
                "  1. T\u1eaft read-only\n"
                "  2. D\u00f9ng diskpart CLEAN (x\u00f3a to\u00e0n b\u1ed9 ph\u00e2n v\u00f9ng)\n"
                "  3. T\u1ea1o ph\u00e2n v\u00f9ng m\u1edbi\n"
                f"  4. Format voi\u0323 {fs}\n\n"
                "T\u1ea5t c\u1ea3 d\u1eef li\u1ec7u s\u1ebd b\u1ecb X\u00d3A HO\u00c0N TO\u00c0N!\n\n"
                "Ch\u1ec9 d\u00f9ng khi format th\u00f4ng th\u01b0\u1eddng KH\u00d4NG HO\u1ea0T \u0110\u1ed8NG.",
                on_yes=lambda: self._do_force_format(letter, fs),
                yes_text="Format b\u1eaft bu\u1ed9c",
                no_text="H\u1ee7y",
            )
        else:
            self._do_force_format(letter, fs)

    def _do_force_format(self, letter, fs="exFAT"):
        self.log_text.append(f"\u0110ang format b\u1eaft bu\u1ed9c \u1ed9 {letter}: voi\u0323 {fs}...")
        self.force_format_btn.setEnabled(False)
        self.force_format_btn.setText(f"{ICONS['x']} \u0110ang format...")
        result = tools.force_format(letter, fs)
        ok = result.get("success", False)
        output = result.get("output", "")
        issues = result.get("issues", [])

        for issue in issues:
            self.log_text.append(f"  {issue}")

        self.log_text.append(f"  K\u1ebft qu\u1ea3: {'Th\u00e0nh c\u00f4ng' if ok else 'L\u1ed7i'}")
        if output:
            self.log_text.append(f"  {output[:500]}")

        parent = self.window()
        if hasattr(parent, 'message_modal'):
            if ok:
                parent.message_modal.success(
                    "Format xong",
                    f"\u0110\u00e3 format b\u1eaft bu\u1ed9c \u1ed9 {letter}: voi\u0323 {fs}.\n\nB\u1ea1n c\u00f3 th\u1ec3 s\u1eed d\u1ee5ng \u0111\u01b0\u1eddng d\u1eabn {letter}:\\",
                    on_ok=lambda: self._scan_drives(),
                )
            else:
                parent.message_modal.error(
                    "L\u1ed7i format",
                    f"Kh\u00f4ng th\u1ec3 format b\u1eaft bu\u1ed9c \u1ed9 {letter}:.\n\n{output[:300]}",
                )
        self.force_format_btn.setEnabled(True)
        self.force_format_btn.setText(f"{ICONS['x']} Format b\u1eaft bu\u1ed9c")
        self._diagnose()


# --------------------------------------------------------------------------- #
# CDriveCleanerPanel - Xóa file/thư mục vĩnh viễn (mọi ổ đĩa, không qua thùng rác)
# --------------------------------------------------------------------------- #

class CDriveCleanerPanel(ToolPanel):
    def __init__(self, parent=None):
        super().__init__("X\u00f3a v\u0129nh vi\u1ec5n", "X\u00f3a file/th\u01b0 m\u1ee5c tr\u1ef1c ti\u1ebfp KH\u00d4NG qua th\u00f9ng r\u00e1c \u1ed5 C: (\u00e1p d\u1ee5ng m\u1ecdi \u1ed5 \u0111\u0129a). Gi\u1ea3i ph\u00f3ng dung l\u01b0\u1ee3ng ngay, tr\u00e1nh \u1ed5 C: \u0111\u1ea7y g\u00e2y l\u1ed7i Windows.", "trash", parent)
        self._locations = []
        self._current_path = ""

        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton(f"{ICONS['search']} Qu\u00e9t r\u00e1c \u1ed5 C:")
        self.scan_btn.setObjectName("PrimaryButton")
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self.scan_btn)

        self.browse_btn = QPushButton(f"{ICONS['folder']} Ch\u1ecdn th\u01b0 m\u1ee5c...")
        self.browse_btn.setObjectName("SecondaryButton")
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.clicked.connect(self._browse_folder)
        btn_row.addWidget(self.browse_btn)

        self.browse_file_btn = QPushButton(f"{ICONS['folder']} Ch\u1ecdn t\u1eadp tin...")
        self.browse_file_btn.setObjectName("SecondaryButton")
        self.browse_file_btn.setCursor(Qt.PointingHandCursor)
        self.browse_file_btn.clicked.connect(self._browse_file)
        btn_row.addWidget(self.browse_file_btn)

        self.delete_btn = QPushButton(f"{ICONS['trash']} X\u00f3a v\u0129nh vi\u1ec5n")
        self.delete_btn.setObjectName("DangerButton")
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._force_delete)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch(1)
        self.content_layout.addLayout(btn_row)

        self.custom_path_edit = QLineEdit()
        self.custom_path_edit.setPlaceholderText("Nh\u1eadp \u0111\u01b0\u1eddng d\u1eabn file/th\u01b0 m\u1ee5c b\u1ea5t k\u1ef3 (vd: D:\\Folder, E:\\file.avi)...")
        self.custom_path_edit.setObjectName("ToolSearch")
        self.custom_path_edit.textChanged.connect(self._on_path_changed)
        self.content_layout.addWidget(self.custom_path_edit)

        warn = QFrame()
        warn.setObjectName("ToolWarning")
        wl = QHBoxLayout(warn)
        wl.setContentsMargins(12, 8, 12, 8)
        wt = QLabel(f"{ICONS['warning']}  C\u1ea3nh b\u00e1o: X\u00f3a V\u0128NH VI\u1ec4N, kh\u00f4ng qua th\u00f9ng r\u00e1c \u1ed5 C:. D\u00f9 \u1edf \u1ed5 D:, E:, ... c\u0169ng kh\u00f4ng \u0111\u1ea9y v\u00e0o th\u00f9ng r\u00e1c C:, tr\u00e1nh \u0111\u1ea7y \u1ed5 C: l\u00e0m l\u1ed7i Windows!")
        wt.setObjectName("ToolWarningText")
        wt.setWordWrap(True)
        wl.addWidget(wt, 1)
        self.content_layout.addWidget(warn)

        self.status_label = QLabel("Ch\u1ecdn \u0111\u01b0\u1eddng d\u1eabn ho\u1eb7c qu\u00e9t r\u00e1c \u1ed5 C:.")
        self.status_label.setObjectName("ToolStatusLabel")
        self.content_layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setObjectName("ScanProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.content_layout.addWidget(self.progress)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["V\u1ecb tr\u00ed", "\u0110\u01b0\u1eddng d\u1eabn", "S\u1ed1 file", "Dung l\u01b0\u1ee3ng"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setObjectName("ToolTable")
        self.table.itemSelectionChanged.connect(self._on_sel)
        self.content_layout.addWidget(self.table, 1)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("ToolOutput")
        self.log_text.setMaximumHeight(140)
        self.log_text.setPlaceholderText("Nh\u1eadt k\u00fd ho\u1ea1t \u0111\u1ed9ng...")
        self.content_layout.addWidget(self.log_text)

    def _on_path_changed(self, text):
        self._current_path = text.strip()
        self.delete_btn.setEnabled(bool(self._current_path))

    def _start_scan(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(f"{ICONS['search']} \u0110ang qu\u00e9t...")
        self.delete_btn.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        self.table.setRowCount(0)
        self.log_text.clear()
        self.log_text.append("B\u1eaft \u0111\u1ea7u qu\u00e9t c\u00e1c th\u01b0 m\u1ee5c r\u00e1c tr\u00ean \u1ed5 C:...")

        self._worker = CDriveScanWorker()
        self._worker.finished.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self, locations):
        self._locations = locations
        self.table.setRowCount(len(locations))
        total_size = 0
        for row, loc in enumerate(locations):
            self.table.setItem(row, 0, QTableWidgetItem(loc["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(loc["path"]))
            self.table.setItem(row, 2, QTableWidgetItem(str(loc["file_count"])))
            size_str = self._fmt(loc["size_bytes"])
            self.table.setItem(row, 3, QTableWidgetItem(size_str))
            total_size += loc["size_bytes"]
            self.log_text.append(f"  {loc['name']}: {loc['file_count']} file, {size_str}")

        self.progress.setValue(100)
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText(f"{ICONS['search']} Qu\u00e9t r\u00e1c \u1ed5 C:")
        self.status_label.setText(f"T\u00ecm th\u1ea5y {len(locations)} th\u01b0 m\u1ee5c r\u00e1c tr\u00ean C:. T\u1ed5ng: {self._fmt(total_size)}")
        self.log_text.append(f"Ho\u00e0n t\u1ea5t. T\u00ecm th\u1ea5y {len(locations)} th\u01b0 m\u1ee5c r\u00e1c.")

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Ch\u1ecdn th\u01b0 m\u1ee5c c\u1ea7n x\u00f3a v\u0129nh vi\u1ec5n (m\u1ecdi \u1ed5 \u0111\u0129a)")
        if path:
            self.custom_path_edit.setText(path)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ch\u1ecdn t\u1eadp tin c\u1ea7n x\u00f3a v\u0129nh vi\u1ec5n (m\u1ecdi \u1ed5 \u0111\u0129a)")
        if path:
            self.custom_path_edit.setText(path)

    def _on_sel(self):
        if self.table.selectedItems():
            row = self.table.currentRow()
            if row >= 0 and row < len(self._locations):
                self.custom_path_edit.setText(self._locations[row]["path"])

    def _force_delete(self):
        path = self._current_path
        if not path:
            return
        if not os.path.exists(path):
            parent = self.window()
            if hasattr(parent, 'message_modal'):
                parent.message_modal.error("L\u1ed7i", "\u0110\u01b0\u1eddng d\u1eabn kh\u00f4ng t\u1ed3n t\u1ea1i!")
            return

        protected, protected_name = tools._is_protected_path(path)
        if protected:
            parent = self.window()
            msg = f"T\u1eea CH\u1ed0I: '{path}'\n\n\u0110\u00e2y l\u00e0 th\u01b0 m\u1ee5c h\u1ec7 th\u1ed1ng quan tr\u1ecdng: {protected_name}\nKh\u00f4ng th\u1ec3 x\u00f3a v\u00ec s\u1ebd g\u00e2y l\u1ed7i Windows!"
            if hasattr(parent, 'message_modal'):
                parent.message_modal.error("Kh\u00f4ng th\u1ec3 x\u00f3a!", msg)
            else:
                self.status_label.setText(f"{ICONS['x']} {msg}")
            self.log_text.append(f"{ICONS['x']} T\u1eea CH\u1ed0I x\u00f3a th\u01b0 m\u1ee5c h\u1ec7 th\u1ed1ng: {path}")
            return

        self._pending_path = path
        parent = self.window()
        if hasattr(parent, 'message_modal'):
            parent.message_modal.confirm(
                "X\u00e1c nh\u1eadn x\u00f3a V\u0128NH VI\u1ec4N",
                f"B\u1ea1n c\u00f3 CH\u1eaeC ch\u1eafn mu\u1ed1n x\u00f3a v\u0129nh vi\u1ec5n (kh\u00f4ng qua th\u00f9ng r\u00e1c):\n\n{path}\n\nThao t\u00e1c n\u00e0y KH\u00d4NG TH\u1ec2 ho\u00e0n t\u00e1c!",
                on_yes=self._do_delete,
                yes_text="X\u00f3a v\u0129nh vi\u1ec5n",
                no_text="H\u1ee7y",
            )

    def _do_delete(self):
        path = getattr(self, '_pending_path', '')
        if not path:
            return
        self.delete_btn.setEnabled(False)
        self.table.setEnabled(False)
        self.delete_btn.setText(f"{ICONS['trash']} \u0110ang x\u00f3a...")
        self.log_text.append(f"\u0110ang x\u00f3a v\u0129nh vi\u1ec5n: {path}...")

        result = tools.permanent_delete(path)
        parent = self.window()

        if result.get("success"):
            msg = f"{ICONS['check']} {result.get('output', '\u0110\u00e3 x\u00f3a th\u00e0nh c\u00f4ng.')}"
            self.status_label.setText(msg)
            self.log_text.append(msg)
            self.custom_path_edit.clear()
            if hasattr(parent, 'message_modal'):
                parent.message_modal.success("Th\u00e0nh c\u00f4ng", result.get('output', '\u0110\u00e3 x\u00f3a.'))
        else:
            msg = f"{ICONS['x']} {result.get('error', 'L\u1ed7i.')}"
            self.status_label.setText(msg)
            self.log_text.append(msg)
            if hasattr(parent, 'message_modal'):
                parent.message_modal.error("L\u1ed7i", result.get('error', 'Kh\u00f4ng th\u1ec3 x\u00f3a.'))

        self.delete_btn.setText(f"{ICONS['trash']} X\u00f3a v\u0129nh vi\u1ec5n")
        self.delete_btn.setEnabled(True)
        self.table.setEnabled(True)

    def _fmt(self, b: int) -> str:
        for u in ["B", "KB", "MB", "GB"]:
            if b < 1024:
                return f"{b:.1f} {u}"
            b /= 1024
        return f"{b:.1f} TB"


# --------------------------------------------------------------------------- #
# Port Detector Panel
# --------------------------------------------------------------------------- #

class PortDetectorPanel(ToolPanel):
    def __init__(self, parent=None):
        super().__init__("Ph\u00e1t hi\u1ec7n c\u1ed5ng ngo\u00e0i", "T\u1ef1 \u0111\u1ed9ng ph\u00e1t hi\u1ec7n USB, Serial, Bluetooth, Network.", "usb", parent)

        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton(f"{ICONS['refresh']} Qu\u00e9t c\u1ed5ng")
        self.scan_btn.setObjectName("PrimaryButton")
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self.scan_btn)
        btn_row.addStretch(1)
        self.content_layout.addLayout(btn_row)

        self.status_label = QLabel("Nh\u1ea5n \"Qu\u00e9t c\u1ed5ng\" \u0111\u1ec3 b\u1eaft \u0111\u1ea7u.")
        self.status_label.setObjectName("ToolStatusLabel")
        self.content_layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setObjectName("ScanProgress")
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.content_layout.addWidget(self.progress)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Lo\u1ea1i", "T\u00ean", "M\u00f4 t\u1ea3", "Tr\u1ea1ng th\u00e1i"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setObjectName("ToolTable")
        self.content_layout.addWidget(self.table, 1)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("ToolOutput")
        self.log_text.setMaximumHeight(140)
        self.log_text.setPlaceholderText("Nh\u1eadt k\u00fd ph\u00e1t hi\u1ec7n...")
        self.content_layout.addWidget(self.log_text)

    def _start_scan(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(f"{ICONS['refresh']} \u0110ang qu\u00e9t...")
        self.table.setRowCount(0)
        self.progress.show()
        self.log_text.append("B\u1eaft \u0111\u1ea7u qu\u00e9t c\u1ed5ng k\u1ebft n\u1ed1i...")

        self._worker = PortScanWorker()
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_done(self, result):
        self.progress.hide()
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText(f"{ICONS['refresh']} Qu\u00e9t c\u1ed5ng")

        all_devices = []
        for d in result.get("serial_ports", []):
            all_devices.append(d)
            self.log_text.append(f"  Serial: {d.get('name', '')} - {d.get('description', '')}")
        for d in result.get("usb_devices", []):
            all_devices.append(d)
            self.log_text.append(f"  USB: {d.get('name', '')}")
        for d in result.get("network_adapters", []):
            d["type"] = "Network"
            all_devices.append(d)
            self.log_text.append(f"  Network: {d.get('name', '')} - {d.get('speed', '')}")
        for d in result.get("bluetooth", []):
            d["type"] = "Bluetooth"
            d["description"] = d.get("id", "")
            all_devices.append(d)
            self.log_text.append(f"  Bluetooth: {d.get('name', '')}")

        self.table.setRowCount(len(all_devices))
        for r, d in enumerate(all_devices):
            self.table.setItem(r, 0, QTableWidgetItem(d.get("type", "")))
            self.table.setItem(r, 1, QTableWidgetItem(d.get("name", "")))
            self.table.setItem(r, 2, QTableWidgetItem(d.get("description", "")))
            self.table.setItem(r, 3, QTableWidgetItem(d.get("status", "")))

        total = len(all_devices)
        self.status_label.setText(f"T\u00ecm th\u1ea5y {total} thi\u1ebft b\u1ecb/c\u1ed5ng k\u1ebft n\u1ed1i.")
        self.log_text.append(f"Ho\u00e0n t\u1ea5t: {total} thi\u1ebft b\u1ecb.")


# --------------------------------------------------------------------------- #
# Windows Repair Panel - SFC, DISM, chkdsk
# --------------------------------------------------------------------------- #

class WindowsRepairPanel(ToolPanel):
    def __init__(self, parent=None):
        super().__init__("S\u1eeda ch\u1eefa Windows", "Qu\u00e9t v\u00e0 s\u1eeda l\u1ed7i h\u1ec7 th\u1ed1ng: SFC, DISM, chkdsk.", "shield", parent)
        self._output = ""

        btn_row = QHBoxLayout()
        self.sfc_btn = _icon_btn("SFC /scannow", "search", "PrimaryButton")
        self.sfc_btn.clicked.connect(self._run_sfc)
        btn_row.addWidget(self.sfc_btn)

        self.dism_scan_btn = _icon_btn("DISM ScanHealth", "search", "SecondaryButton")
        self.dism_scan_btn.clicked.connect(self._run_dism_scan)
        btn_row.addWidget(self.dism_scan_btn)

        self.dism_btn = _icon_btn("DISM RestoreHealth", "search", "DangerButton")
        self.dism_btn.clicked.connect(self._run_dism_restore)
        btn_row.addWidget(self.dism_btn)

        self.chkdsk_btn = _icon_btn("chkdsk C:", "search", "SecondaryButton")
        self.chkdsk_btn.clicked.connect(self._run_chkdsk)
        btn_row.addWidget(self.chkdsk_btn)
        btn_row.addStretch(1)
        self.content_layout.addLayout(btn_row)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setObjectName("ToolOutput")
        self.result_text.setPlaceholderText("K\u1ebft qu\u1ea3 ki\u1ec3m tra...")
        self.content_layout.addWidget(self.result_text, 1)

    def _run_sfc(self):
        self.sfc_btn.setEnabled(False)
        self.result_text.append(">>> \u0110ang ch\u1ea1y SFC /scannow (c\u00f3 th\u1ec3 m\u1ea5t v\u00e0i ph\u00fat)...")
        self._worker = SfcWorker()
        self._worker.finished.connect(lambda r: self._on_done(r, "SFC"))
        self._worker.start()

    def _run_dism_scan(self):
        self.dism_scan_btn.setEnabled(False)
        self.result_text.append(">>> \u0110ang ch\u1ea1y DISM ScanHealth...")
        self._worker = DismScanWorker()
        self._worker.finished.connect(lambda r: self._on_done(r, "DISM ScanHealth"))
        self._worker.start()

    def _run_dism_restore(self):
        self.dism_btn.setEnabled(False)
        self.result_text.append(">>> \u0110ang ch\u1ea1y DISM RestoreHealth (c\u00f3 th\u1ec3 m\u1ea5t nhi\u1ec1u ph\u00fat)...")
        self._worker = DismRestoreWorker()
        self._worker.finished.connect(lambda r: self._on_done(r, "DISM RestoreHealth"))
        self._worker.start()

    def _run_chkdsk(self):
        self.chkdsk_btn.setEnabled(False)
        self.result_text.append(">>> \u0110ang ch\u1ea1y chkdsk C: /f...")
        self._worker = ChkdskWorker("C:")
        self._worker.finished.connect(lambda r: self._on_done(r, "chkdsk"))
        self._worker.start()

    def _on_done(self, result, name):
        out = result.get("output", "")
        self.result_text.append(f"K\u1ebft th\u00fac {name}:\n{out}\n")
        self.sfc_btn.setEnabled(True)
        self.dism_scan_btn.setEnabled(True)
        self.dism_btn.setEnabled(True)
        self.chkdsk_btn.setEnabled(True)


# --------------------------------------------------------------------------- #
# Firewall Panel
# --------------------------------------------------------------------------- #

class FirewallPanel(ToolPanel):
    def __init__(self, parent=None):
        super().__init__("T\u01b0\u1eddng l\u1eeda", "B\u1eadt/t\u1eaft nhanh t\u01b0\u1eddng l\u1eeda Windows Defender (kh\u00f4ng th\u00f4ng b\u00e1o).", "shield", parent)

        btn_row = QHBoxLayout()
        self.status_label_widget = QLabel("\u0110ang ki\u1ec3m tra tr\u1ea1ng th\u00e1i...")
        self.status_label_widget.setObjectName("ToolStatusLabel")
        btn_row.addWidget(self.status_label_widget)
        btn_row.addStretch(1)

        self.toggle_btn = QPushButton()
        self.toggle_btn.setObjectName("DangerButton")
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setFixedHeight(36)
        self.toggle_btn.clicked.connect(self._toggle)
        btn_row.addWidget(self.toggle_btn)
        self.content_layout.addLayout(btn_row)

        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setObjectName("ToolOutput")
        self.info_text.setPlaceholderText("Tr\u1ea1ng th\u00e1i t\u01b0\u1eddng l\u1eeda...")
        self.content_layout.addWidget(self.info_text, 1)
        self.content_layout.addStretch(1)

        self._on = False
        self._check_status()

    def _check_status(self):
        self._worker = FirewallStatusWorker()
        self._worker.finished.connect(self._on_status)
        self._worker.start()

    def _on_status(self, result):
        self._on = result.get("enabled", False)
        self._update_ui()
        self.info_text.append(f"Tr\u1ea1ng th\u00e1i t\u01b0\u1eddng l\u1eeda: {'B\u1eacT' if self._on else 'T\u1eaeT'}")
        if result.get("output"):
            self.info_text.append(result["output"])

    def _toggle(self):
        self.toggle_btn.setEnabled(False)
        target = not self._on
        self.info_text.append(f"\u0110ang {'t\u1eaft' if not target else 'b\u1eadt'} t\u01b0\u1eddng l\u1eeda...")
        self._worker = FirewallToggleWorker(target)
        self._worker.finished.connect(self._on_toggle_done)
        self._worker.start()

    def _on_toggle_done(self, result):
        self._on = result.get("enabled", False)
        self._update_ui()
        self.info_text.append(f"\u0110\u00e3 {'t\u1eaft' if not self._on else 'b\u1eadt'} t\u01b0\u1eddng l\u1eeda.")
        self.toggle_btn.setEnabled(True)

    def _update_ui(self):
        if self._on:
            self.toggle_btn.setText("T\u1eaeT t\u01b0\u1eddng l\u1eeda")
            self.toggle_btn.setObjectName("DangerButton")
        else:
            self.toggle_btn.setText("B\u1eacT t\u01b0\u1eddng l\u1eeda")
            self.toggle_btn.setObjectName("PrimaryButton")
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)
        self.status_label_widget.setText(
            f"Tr\u1ea1ng th\u00e1i: {'\u2705 \u0110ANG B\u1eacT' if self._on else '\u26A0 \u0110ANG T\u1eAET'}"
        )


# --------------------------------------------------------------------------- #
# Driver Scanner Panel
# --------------------------------------------------------------------------- #

class DriverScannerPanel(ToolPanel):
    def __init__(self, parent=None):
        super().__init__("Qu\u00e9t Driver", "Li\u1ec7t k\u00ea t\u1ea5t c\u1ea3 driver, ph\u00e1t hi\u1ec7n driver c\u0169 c\u1ea7n c\u1eadp nh\u1eadt.", "search", parent)
        self._drivers = []

        btn_row = QHBoxLayout()
        self.scan_btn = _icon_btn(f"{ICONS['search']} Qu\u00e9t driver", "", "PrimaryButton")
        self.scan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self.scan_btn)

        self.filter_cb = QComboBox()
        self.filter_cb.addItems(["T\u1ea5t c\u1ea3", "C\u1ea7n c\u1eadp nh\u1eadt"])
        self.filter_cb.currentIndexChanged.connect(self._apply_filter)
        btn_row.addWidget(self.filter_cb)

        btn_row.addStretch(1)
        self.content_layout.addLayout(btn_row)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Driver", "Nh\u00e0 cung c\u1ea5p", "L\u1edbp", "Phi\u00ean b\u1ea3n", "Ng\u00e0y", "Tr\u1ea1ng th\u00e1i"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setObjectName("ToolTable")
        self.content_layout.addWidget(self.table, 1)

        self.status_label = QLabel("Nh\u1ea5n \"Qu\u00e9t driver\" \u0111\u1ec3 li\u1ec7t k\u00ea.")
        self.status_label.setObjectName("ToolStatusLabel")
        self.content_layout.addWidget(self.status_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("ToolOutput")
        self.log_text.setMaximumHeight(120)
        self.log_text.setPlaceholderText("Nh\u1eadt k\u00fd qu\u00e9t...")
        self.content_layout.addWidget(self.log_text)

    def _start_scan(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText(f"\u0110ang qu\u00e9t...")
        self.table.setRowCount(0)
        self.log_text.clear()
        self.log_text.append("\u0110ang qu\u00e9t driver b\u1eb1ng pnputil...")
        self._worker = DriverScanWorker()
        self._worker.finished.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self, drivers):
        self._drivers = drivers
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText(f"{ICONS['search']} Qu\u00e9t driver")

        outdated = sum(1 for d in drivers if d.get("needs_update"))
        self.status_label.setText(
            f"T\u00ecm th\u1ea5y {len(drivers)} driver, {outdated} c\u1ea7n c\u1eadp nh\u1eadt."
        )
        self.log_text.append(
            f"Ho\u00e0n t\u1ea5t: {len(drivers)} driver, {outdated} c\u0169 h\u01a1n 1 n\u0103m."
        )
        self._apply_filter()

    def _apply_filter(self):
        mode = self.filter_cb.currentText()
        if mode == "C\u1ea7n c\u1eadp nh\u1eadt":
            filtered = [d for d in self._drivers if d.get("needs_update")]
        else:
            filtered = self._drivers

        self.table.setRowCount(len(filtered))
        for r, d in enumerate(filtered):
            name = d.get("Original Name", d.get("Published Name", ""))
            provider = d.get("Provider Name", "")
            drv_class = d.get("Class Name", "")
            version = d.get("Driver Version", "")
            date = d.get("driver_date", "")
            needs = d.get("needs_update", False)
            self.table.setItem(r, 0, QTableWidgetItem(name))
            self.table.setItem(r, 1, QTableWidgetItem(provider))
            self.table.setItem(r, 2, QTableWidgetItem(drv_class))
            ver_parts = version.split(" ", 1)
            ver_display = ver_parts[1] if len(ver_parts) > 1 else version
            self.table.setItem(r, 3, QTableWidgetItem(ver_display))
            self.table.setItem(r, 4, QTableWidgetItem(date))
            if needs:
                item = QTableWidgetItem("C\u1ea7n c\u1eadp nh\u1eadt")
                item.setForeground(Qt.red)
            else:
                item = QTableWidgetItem("M\u1edbi nh\u1ea5t")
                item.setForeground(Qt.green)
            self.table.setItem(r, 5, item)
