"""
scanner.py
----------
Chạy toàn bộ các hàm dò quét trong app.core.detectors bên trong một
QThread riêng để giao diện không bị đóng băng trong lúc quét.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.core import detectors as det


class ScanWorker(QThread):
    step_started = Signal(str, str)          # (key, label)
    step_finished = Signal(str, object)       # (key, ScanSection)
    progress = Signal(int, int)               # (current, total)
    finished_all = Signal(dict, str, int, str)  # (sections, verdict, score, desc)
    failed = Signal(str)

    def run(self) -> None:  # noqa: D102
        try:
            sections: dict[str, det.ScanSection] = {}
            steps = [
                ("win_activation", det.check_windows_activation, ()),
                ("office_activation", det.check_office_activation, ()),
                ("bios_oem_key", None, None),  # cần kết quả win_activation -> xử lý riêng
                ("registry_traces", det.scan_registry_traces, ()),
                ("scheduled_tasks", det.scan_scheduled_tasks, ()),
                ("services", det.scan_services, ()),
                ("filesystem_traces", det.scan_filesystem_traces, ()),
            ]
            total = len(steps)

            for i, (key, fn, args) in enumerate(steps, start=1):
                label = det.SECTION_LABELS.get(key, key)
                self.step_started.emit(key, label)

                if key == "bios_oem_key":
                    section = det.check_bios_oem_key(sections.get("win_activation"))
                else:
                    section = fn(*args)  # type: ignore[misc]

                sections[key] = section
                self.step_finished.emit(key, section)
                self.progress.emit(i, total)

            verdict, score, desc = det.compute_verdict(sections)
            self.finished_all.emit(sections, verdict, score, desc)

        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
