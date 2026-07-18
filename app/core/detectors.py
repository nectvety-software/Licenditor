"""
detectors.py
------------
Bộ dò quét (audit) tình trạng bản quyền Windows / Office.

Mục tiêu: xác định xem một máy được báo "Activated" / "Đã kích hoạt" có
thực sự hợp lệ hay không, bằng cách đối chiếu NHIỀU nguồn dữ liệu:

  1. Trạng thái kích hoạt qua slmgr.vbs / ospp.vbs (kênh cấp phép: Retail,
     OEM:NONSLP, OEM:DM, Volume:GVLK, Volume:MAK...)
  2. Khóa OEM nhúng trong BIOS/UEFI (bảng ACPI MSDM) qua
     SoftwareLicensingService.OA3xOriginalProductKey
  3. Dấu vết registry thường bị các công cụ kích hoạt lậu (KMSpico,
     KMSAuto/KMSAuto Net, Re-Loader, HWIDGEN, MAS - Microsoft Activation
     Scripts, ODIN, HEU KMS Activator...) để lại
  4. Scheduled Task lạ dùng để "rearm"/gia hạn KMS giả định kỳ
  5. Windows Service lạ dùng để giả lập máy chủ KMS nội bộ (loopback)
  6. Tàn dư file/thư mục của các bộ công cụ kích hoạt phổ biến

Toàn bộ hàm đều được viết theo kiểu "best effort": nếu chạy trên hệ điều
hành không phải Windows, hoặc thiếu quyền, hàm sẽ trả về kết quả rỗng kèm
ghi chú lỗi thay vì crash toàn bộ chương trình.
"""

from __future__ import annotations

import os
import re
import sys
import glob
import locale
import subprocess
from dataclasses import dataclass, field
from typing import Any

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import winreg  # type: ignore
else:
    winreg = None  # type: ignore


# --------------------------------------------------------------------------- #
# Cấu trúc dữ liệu kết quả
# --------------------------------------------------------------------------- #

@dataclass
class Finding:
    """Một dấu hiệu/bằng chứng đơn lẻ được phát hiện."""
    severity: str          # "info" | "warning" | "danger"
    title: str
    detail: str


@dataclass
class ScanSection:
    """Kết quả của một hạng mục quét (vd: Windows Activation)."""
    key: str
    label: str
    status: str = "unknown"      # "clean" | "warning" | "danger" | "unknown"
    summary: str = ""
    findings: list[Finding] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Tiện ích chạy lệnh hệ thống
# --------------------------------------------------------------------------- #

def _run(cmd: list[str] | str, shell: bool = False, timeout: int = 20) -> tuple[bool, str]:
    """Chạy lệnh hệ thống, trả về (thành công?, output_text). Không mở cửa sổ console."""
    creationflags = 0
    startupinfo = None
    if IS_WINDOWS:
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    try:
        out = subprocess.check_output(
            cmd,
            shell=shell,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            creationflags=creationflags,
            startupinfo=startupinfo,
        )
    except Exception as exc:  # noqa: BLE001 - muốn bắt mọi lỗi để không sập UI
        return False, f"__ERROR__ {exc}"

    enc_candidates = ["utf-8", locale.getpreferredencoding(False), "cp1258", "cp850"]
    text = ""
    for enc in enc_candidates:
        try:
            text = out.decode(enc, errors="ignore")
            break
        except Exception:  # noqa: BLE001
            continue
    return True, text


def _powershell(script: str, timeout: int = 20) -> tuple[bool, str]:
    return _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        timeout=timeout,
    )


# --------------------------------------------------------------------------- #
# 1) Windows Activation (slmgr)
# --------------------------------------------------------------------------- #

_CHANNEL_PATTERNS = {
    "RETAIL": "Bán lẻ (Retail)",
    "OEM:NONSLP": "OEM ghim BIOS (OEM:NONSLP)",
    "OEM:COA": "OEM COA (nhãn dán)",
    "OEM:DM": "OEM Digital Marker",
    "VOLUME_KMSCLIENT": "Volume - KMS Client (GVLK)",
    "VOLUME_MAK": "Volume - MAK",
}


def check_windows_activation() -> ScanSection:
    sec = ScanSection(key="win_activation", label="Kích hoạt Windows")

    if not IS_WINDOWS:
        sec.status = "unknown"
        sec.summary = "Chỉ hỗ trợ trên Windows."
        return sec

    system32 = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32")
    slmgr = os.path.join(system32, "slmgr.vbs")

    ok_dli, out_dli = _run(["cscript", "//Nologo", slmgr, "/dli"])
    ok_xpr, out_xpr = _run(["cscript", "//Nologo", slmgr, "/xpr"])

    sec.raw["dli"] = out_dli
    sec.raw["xpr"] = out_xpr

    if not ok_dli:
        sec.status = "unknown"
        sec.summary = "Không thể truy vấn slmgr.vbs (thiếu quyền hoặc bị chặn)."
        sec.findings.append(Finding("warning", "Không đọc được trạng thái",
                                     "Hãy chạy ứng dụng với quyền Administrator."))
        return sec

    name_match = re.search(r"Name:\s*(.+)", out_dli)
    desc_match = re.search(r"Description:\s*(.+)", out_dli)
    status_match = re.search(r"License Status:\s*(.+)", out_dli)
    partial_key_match = re.search(r"Partial Product Key:\s*(.+)", out_dli)

    license_status = status_match.group(1).strip() if status_match else "Không rõ"
    description = desc_match.group(1).strip() if desc_match else ""
    partial_key = partial_key_match.group(1).strip() if partial_key_match else ""

    channel = "Không xác định"
    for pat, label in _CHANNEL_PATTERNS.items():
        if pat in description:
            channel = label
            break

    displays_activated = "licensed" in license_status.lower() or "permanently activated" in out_xpr.lower()

    sec.raw.update({
        "license_status": license_status,
        "description": description,
        "partial_product_key": partial_key,
        "channel": channel,
        "displays_activated": displays_activated,
    })

    if displays_activated:
        sec.findings.append(Finding(
            "info", "Hệ thống báo cáo đã kích hoạt",
            f'License Status: "{license_status}" | Kênh cấp phép: {channel} | '
            f'Khóa (5 ký tự cuối): {partial_key or "N/A"}',
        ))
        sec.status = "clean"
        sec.summary = f"Đã kích hoạt qua kênh: {channel}"
    else:
        sec.findings.append(Finding(
            "danger", "Chưa được kích hoạt hợp lệ",
            f'License Status trả về: "{license_status}"',
        ))
        sec.status = "danger"
        sec.summary = "Không tìm thấy bản quyền hợp lệ."

    return sec


# --------------------------------------------------------------------------- #
# 2) Office Activation (ospp.vbs)
# --------------------------------------------------------------------------- #

def _find_ospp_paths() -> list[str]:
    roots = [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]
    found: list[str] = []
    for root in roots:
        if not root:
            continue
        pattern = os.path.join(root, "Microsoft Office", "Office*", "ospp.vbs")
        found.extend(glob.glob(pattern))
    return found


def check_office_activation() -> ScanSection:
    sec = ScanSection(key="office_activation", label="Kích hoạt Microsoft Office")

    if not IS_WINDOWS:
        sec.status = "unknown"
        sec.summary = "Chỉ hỗ trợ trên Windows."
        return sec

    ospp_paths = _find_ospp_paths()
    if not ospp_paths:
        sec.status = "unknown"
        sec.summary = "Không tìm thấy Office (ospp.vbs) trên máy."
        return sec

    any_licensed = False
    channels: set[str] = set()
    blocks: list[str] = []

    for ospp in ospp_paths:
        ok, out = _run(["cscript", "//Nologo", ospp, "/dstatus"])
        if not ok:
            continue
        blocks.append(out)
        for m in re.finditer(r"LICENSE STATUS:\s*-+\s*(.+)", out):
            if "LICENSED" in m.group(1).upper():
                any_licensed = True
        for m in re.finditer(r"LICENSE NAME:\s*(.+)", out):
            channels.add(m.group(1).strip())

    sec.raw["dstatus_blocks"] = blocks
    sec.raw["channels"] = sorted(channels)

    if any_licensed:
        sec.status = "clean"
        sec.summary = "Office báo cáo đã kích hoạt (LICENSED)."
        sec.findings.append(Finding(
            "info", "Office đã kích hoạt",
            "Kênh cấp phép phát hiện: " + (", ".join(channels) if channels else "không rõ"),
        ))
    else:
        sec.status = "warning"
        sec.summary = "Không xác nhận được Office đã kích hoạt hợp lệ."
        sec.findings.append(Finding(
            "warning", "Không tìm thấy trạng thái LICENSED",
            "Có thể Office chưa cài, chưa kích hoạt, hoặc dùng bản dùng thử.",
        ))

    return sec


# --------------------------------------------------------------------------- #
# 3) Khóa OEM nhúng BIOS/UEFI (bảng ACPI MSDM)
# --------------------------------------------------------------------------- #

def check_bios_oem_key(win_activation: ScanSection | None = None) -> ScanSection:
    sec = ScanSection(key="bios_oem_key", label="Khóa OEM nhúng BIOS")

    if not IS_WINDOWS:
        sec.status = "unknown"
        sec.summary = "Chỉ hỗ trợ trên Windows."
        return sec

    ok, out = _powershell(
        "(Get-CimInstance -ClassName SoftwareLicensingService)."
        "OA3xOriginalProductKey"
    )
    key = out.strip() if ok else ""
    sec.raw["oa3x_key"] = key

    if not ok or not key:
        sec.status = "unknown"
        sec.summary = "Không đọc được khóa OEM trong BIOS (máy có thể không phải OEM, hoặc cần quyền Admin)."
        sec.findings.append(Finding(
            "info", "Không tìm thấy MSDM/OA3x key",
            "Bình thường với PC tự lắp ráp hoặc bản Retail/Volume không nhúng BIOS.",
        ))
        return sec

    sec.findings.append(Finding(
        "info", "Tìm thấy khóa OEM trong BIOS/UEFI",
        f"Khóa OA3x: {key}",
    ))

    channel = ""
    if win_activation is not None:
        channel = str(win_activation.raw.get("channel", ""))

    if channel and "OEM" not in channel and "Không xác định" not in channel:
        sec.status = "warning"
        sec.summary = "Máy có khóa OEM trong BIOS nhưng Windows lại kích hoạt qua kênh khác."
        sec.findings.append(Finding(
            "warning", "Kênh kích hoạt không khớp khóa BIOS",
            f"BIOS có khóa OEM nhưng Windows báo kích hoạt qua: {channel}. "
            "Đây có thể là dấu hiệu công cụ kích hoạt bên thứ ba đã ghi đè trạng thái license.",
        ))
    else:
        sec.status = "clean"
        sec.summary = "Khóa OEM trong BIOS khớp với kênh kích hoạt OEM."

    return sec


# --------------------------------------------------------------------------- #
# 4) Dấu vết Registry của công cụ kích hoạt lậu
# --------------------------------------------------------------------------- #

# Danh sách từ khóa (không phân biệt hoa/thường) thường xuất hiện trong tên
# registry key/value hoặc DisplayName của các công cụ kích hoạt trái phép
# phổ biến. Đây chỉ là dữ liệu nhận dạng (signature), KHÔNG chứa hướng dẫn
# sử dụng hay tải các công cụ này.
_ACTIVATOR_KEYWORDS = [
    "kmspico", "kmsauto", "kms auto", "kms_auto", "kmself", "kms elder",
    "re-loader", "reloader", "hwidgen", "hwid gen", "microsoft activation scripts",
    "mas_", "\\mas\\", "odin loader", "heu kms", "vlmcsd", "kmspp",
]

_REGISTRY_TARGETS: list[tuple[int, str]] = []
if IS_WINDOWS:
    _REGISTRY_TARGETS = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Services"),
    ]


def _iter_subkey_names(hive: int, path: str):
    try:
        with winreg.OpenKey(hive, path) as key:  # type: ignore[union-attr]
            i = 0
            while True:
                try:
                    yield winreg.EnumKey(key, i)  # type: ignore[union-attr]
                except OSError:
                    break
                i += 1
    except FileNotFoundError:
        return
    except PermissionError:
        return


def _iter_values(hive: int, path: str):
    try:
        with winreg.OpenKey(hive, path) as key:  # type: ignore[union-attr]
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)  # type: ignore[union-attr]
                    yield name, value
                except OSError:
                    break
                i += 1
    except FileNotFoundError:
        return
    except PermissionError:
        return


def scan_registry_traces() -> ScanSection:
    sec = ScanSection(key="registry_traces", label="Dấu vết trong Registry")

    if not IS_WINDOWS:
        sec.status = "unknown"
        sec.summary = "Chỉ hỗ trợ trên Windows."
        return sec

    hits: list[str] = []

    for hive, path in _REGISTRY_TARGETS:
        for sub in _iter_subkey_names(hive, path):
            low = sub.lower()
            if any(kw in low for kw in _ACTIVATOR_KEYWORDS):
                hits.append(f"{path}\\{sub}")
                continue
            # với Uninstall keys, kiểm tra thêm DisplayName bên trong
            if "Uninstall" in path:
                for vname, vval in _iter_values(hive, f"{path}\\{sub}"):
                    if vname == "DisplayName" and isinstance(vval, str):
                        vlow = vval.lower()
                        if any(kw in vlow for kw in _ACTIVATOR_KEYWORDS):
                            hits.append(f"{path}\\{sub} (DisplayName: {vval})")

        for vname, vval in _iter_values(hive, path):
            text = f"{vname}={vval}"
            low = text.lower()
            if any(kw in low for kw in _ACTIVATOR_KEYWORDS):
                hits.append(f"{path} -> {text}")

    # Kiểm tra cờ SkipRearm - kỹ thuật hay bị công cụ kích hoạt lậu bật lên
    try:
        with winreg.OpenKey(  # type: ignore[union-attr]
            winreg.HKEY_LOCAL_MACHINE,  # type: ignore[union-attr]
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\SL",
        ) as key:
            try:
                val, _ = winreg.QueryValueEx(key, "SkipRearm")  # type: ignore[union-attr]
                if val == 1:
                    hits.append(r"HKLM\...\SL -> SkipRearm=1 (bất thường)")
            except FileNotFoundError:
                pass
    except (FileNotFoundError, PermissionError):
        pass

    sec.raw["hits"] = hits

    if hits:
        sec.status = "danger"
        sec.summary = f"Phát hiện {len(hits)} dấu vết registry nghi ngờ."
        for h in hits:
            sec.findings.append(Finding("danger", "Registry nghi ngờ", h))
    else:
        sec.status = "clean"
        sec.summary = "Không tìm thấy dấu vết registry đáng ngờ."

    return sec


# --------------------------------------------------------------------------- #
# 5) Scheduled Task lạ
# --------------------------------------------------------------------------- #

_TASK_KEYWORDS = ["kms", "mas", "hwid", "activator", "reloader", "re-loader", "vlmcsd"]

# Các task hợp lệ của chính Windows liên quan tới licensing - KHÔNG được
# gắn cờ dù có chứa từ khóa gần giống.
_LEGIT_TASK_PREFIXES = [
    "\\Microsoft\\Windows\\SoftwareProtectionPlatform\\",
    r"\Microsoft\Office\Office ",
    r"\Microsoft\Office\OfficeTelemetry",
]


def scan_scheduled_tasks() -> ScanSection:
    sec = ScanSection(key="scheduled_tasks", label="Scheduled Task bất thường")

    if not IS_WINDOWS:
        sec.status = "unknown"
        sec.summary = "Chỉ hỗ trợ trên Windows."
        return sec

    ok, out = _run(["schtasks", "/query", "/fo", "LIST", "/v"], timeout=30)
    if not ok:
        sec.status = "unknown"
        sec.summary = "Không truy vấn được Task Scheduler."
        return sec

    tasks = out.split("\r\n\r\n") if "\r\n\r\n" in out else out.split("\n\n")
    hits: list[str] = []

    for block in tasks:
        name_match = re.search(r"TaskName:\s*(.+)", block)
        if not name_match:
            continue
        name = name_match.group(1).strip()

        if any(name.startswith(p) for p in _LEGIT_TASK_PREFIXES):
            continue

        low = (block).lower()
        if any(kw in low for kw in _TASK_KEYWORDS):
            hits.append(name)

    sec.raw["hits"] = hits

    if hits:
        sec.status = "danger"
        sec.summary = f"Phát hiện {len(hits)} scheduled task nghi ngờ."
        for h in hits:
            sec.findings.append(Finding("danger", "Task nghi ngờ", h))
    else:
        sec.status = "clean"
        sec.summary = "Không có scheduled task bất thường."

    return sec


# --------------------------------------------------------------------------- #
# 6) Service lạ (giả lập KMS nội bộ, hook SPP...)
# --------------------------------------------------------------------------- #

_SERVICE_KEYWORDS = ["kms", "mas", "hwid", "vlmcsd", "activator", "sppextcomobjhook"]


def scan_services() -> ScanSection:
    sec = ScanSection(key="services", label="Windows Services bất thường")

    if not IS_WINDOWS:
        sec.status = "unknown"
        sec.summary = "Chỉ hỗ trợ trên Windows."
        return sec

    ok, out = _run(["sc", "query", "type=", "service", "state=", "all"], timeout=30)
    if not ok:
        sec.status = "unknown"
        sec.summary = "Không truy vấn được danh sách service."
        return sec

    hits: list[str] = []
    for m in re.finditer(r"SERVICE_NAME:\s*(.+)", out):
        name = m.group(1).strip()
        low = name.lower()
        if any(kw in low for kw in _SERVICE_KEYWORDS):
            hits.append(name)

    sec.raw["hits"] = hits

    if hits:
        sec.status = "danger"
        sec.summary = f"Phát hiện {len(hits)} service nghi ngờ."
        for h in hits:
            sec.findings.append(Finding("danger", "Service nghi ngờ", h))
    else:
        sec.status = "clean"
        sec.summary = "Không có service bất thường."

    return sec


# --------------------------------------------------------------------------- #
# 7) Tàn dư file/thư mục công cụ kích hoạt
# --------------------------------------------------------------------------- #

_FS_KEYWORDS = [
    "kmspico", "kmsauto", "kmsauto net", "kmsautonet", "re-loader", "reloader",
    "hwidgen", "microsoft activation scripts", "mas_autorenewal", "heu_kms",
    "odinloader", "vlmcsd",
]

_FS_SCAN_ROOTS = [
    os.environ.get("SystemDrive", "C:") + os.sep,
    os.environ.get("TEMP", ""),
    os.environ.get("ProgramData", ""),
    os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "Users", "Public"),
]


def scan_filesystem_traces(max_depth: int = 2) -> ScanSection:
    sec = ScanSection(key="filesystem_traces", label="Tàn dư file/thư mục")

    if not IS_WINDOWS:
        sec.status = "unknown"
        sec.summary = "Chỉ hỗ trợ trên Windows."
        return sec

    hits: list[str] = []
    seen_roots = {r for r in _FS_SCAN_ROOTS if r}

    for root in seen_roots:
        base_depth = root.rstrip(os.sep).count(os.sep)
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
                if depth >= max_depth:
                    dirnames[:] = []
                    continue
                names_to_check = dirnames + filenames
                for n in names_to_check:
                    low = n.lower()
                    if any(kw in low for kw in _FS_KEYWORDS):
                        hits.append(os.path.join(dirpath, n))
        except (PermissionError, FileNotFoundError):
            continue

    sec.raw["hits"] = hits[:200]

    if hits:
        sec.status = "danger"
        sec.summary = f"Phát hiện {len(hits)} tàn dư file/thư mục nghi ngờ."
        for h in hits[:50]:
            sec.findings.append(Finding("danger", "Tàn dư nghi ngờ", h))
    else:
        sec.status = "clean"
        sec.summary = "Không tìm thấy tàn dư công cụ kích hoạt."

    return sec


# --------------------------------------------------------------------------- #
# Tổng hợp
# --------------------------------------------------------------------------- #

ALL_CHECKS = [
    "win_activation",
    "office_activation",
    "bios_oem_key",
    "registry_traces",
    "scheduled_tasks",
    "services",
    "filesystem_traces",
]

SECTION_LABELS = {
    "win_activation": "Kích hoạt Windows",
    "office_activation": "Kích hoạt Office",
    "bios_oem_key": "Khóa OEM trong BIOS",
    "registry_traces": "Dấu vết Registry",
    "scheduled_tasks": "Scheduled Task",
    "services": "Windows Services",
    "filesystem_traces": "Tàn dư file/thư mục",
}


def activate_oem_key() -> dict:
    """
    Kích hoạt khóa OEM từ BIOS/UEFI vào Windows bằng slmgr.
    Trả về dict với key, status, message.
    """
    if not IS_WINDOWS:
        return {"success": False, "error": "Chỉ hỗ trợ trên Windows."}

    ok, oem_key = _powershell(
        "(Get-CimInstance -ClassName SoftwareLicensingService).OA3xOriginalProductKey"
    )
    oem_key = oem_key.strip() if ok and oem_key.strip() else ""

    if not oem_key:
        return {"success": False, "error": "Không tìm thấy khóa OEM trong BIOS/UEFI.", "oem_key": ""}

    system32 = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32")
    slmgr = os.path.join(system32, "slmgr.vbs")

    ok_install, out_install = _run(["cscript", "//Nologo", slmgr, "/ipk", oem_key])
    if not ok_install:
        return {
            "success": False,
            "error": f"Lỗi cài đặt khóa: {out_install}",
            "oem_key": oem_key,
        }

    ok_activate, out_activate = _run(["cscript", "//Nologo", slmgr, "/ato"])

    win_sec = check_windows_activation()
    current_key = win_sec.raw.get("partial_product_key", "")
    current_channel = win_sec.raw.get("channel", "")

    return {
        "success": True,
        "oem_key": oem_key,
        "oem_partial": oem_key[-5:] if len(oem_key) >= 5 else oem_key,
        "windows_partial": current_key,
        "windows_channel": current_channel,
        "windows_activated": win_sec.status == "clean",
        "message": f"Đã cài đặt khóa OEM. Trạng thái: {win_sec.summary}",
        "install_output": out_install,
        "activate_output": out_activate,
    }


def compare_bios_windows_keys() -> dict:
    """
    So sánh khóa OEM trong BIOS với khóa đang dùng của Windows.
    Trả về dict với thông tin chi tiết.
    """
    if not IS_WINDOWS:
        return {"match": False, "error": "Chỉ hỗ trợ trên Windows."}

    ok, oem_key = _powershell(
        "(Get-CimInstance -ClassName SoftwareLicensingService).OA3xOriginalProductKey"
    )
    oem_key = oem_key.strip() if ok and oem_key.strip() else ""

    system32 = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32")
    slmgr = os.path.join(system32, "slmgr.vbs")
    ok_dli, out_dli = _run(["cscript", "//Nologo", slmgr, "/dli"])

    win_key_partial = ""
    win_channel = ""
    win_status = ""
    if ok_dli:
        m = re.search(r"Partial Product Key:\s*(.+)", out_dli)
        win_key_partial = m.group(1).strip() if m else ""
        m2 = re.search(r"Description:\s*(.+)", out_dli)
        win_channel = m2.group(1).strip() if m2 else ""
        m3 = re.search(r"License Status:\s*(.+)", out_dli)
        win_status = m3.group(1).strip() if m3 else ""

    oem_partial = oem_key[-5:] if len(oem_key) >= 5 else oem_key
    keys_match = (oem_partial == win_key_partial) if (oem_partial and win_key_partial) else False

    return {
        "oem_key": oem_key,
        "oem_partial": oem_partial,
        "windows_partial": win_key_partial,
        "windows_channel": win_channel,
        "windows_status": win_status,
        "keys_match": keys_match,
        "has_oem": bool(oem_key),
        "match_detail": (
            "Khóa OEM khớp với Windows" if keys_match
            else "Khóa OEM KHÔNG khớp với Windows (kênh hiện tại: " + win_channel + ")"
        ),
    }


def compute_verdict(sections: dict[str, ScanSection]) -> tuple[str, int, str]:
    """
    Trả về (verdict, risk_score 0-100, mô tả).
    verdict: "genuine" | "suspect" | "cracked"
    """
    danger_hits = 0
    warning_hits = 0
    windows_ok = sections.get("win_activation")
    windows_ok = bool(windows_ok and windows_ok.status == "clean")

    for sec in sections.values():
        if sec.status == "danger":
            danger_hits += len([f for f in sec.findings if f.severity == "danger"]) or 1
        elif sec.status == "warning":
            warning_hits += 1

    tamper_sections = {"registry_traces", "scheduled_tasks", "services", "filesystem_traces"}
    tamper_evidence = any(
        sections.get(k) is not None and sections[k].status == "danger"
        for k in tamper_sections
    )

    if tamper_evidence:
        score = min(100, 60 + danger_hits * 5)
        return (
            "cracked",
            score,
            "Phát hiện dấu vết công cụ kích hoạt trái phép (KMS emulator / HWID / MAS...). "
            "Dù Windows/Office hiển thị \"Activated\", đây vẫn là bản quyền KHÔNG hợp lệ.",
        )

    if not windows_ok:
        return (
            "cracked",
            80,
            "Windows chưa được kích hoạt hợp lệ theo slmgr.",
        )

    if warning_hits > 0:
        score = min(75, 35 + warning_hits * 10)
        return (
            "suspect",
            score,
            "Có một vài điểm bất nhất giữa các nguồn dữ liệu (vd: khóa BIOS và kênh kích hoạt "
            "không khớp). Nên kiểm tra thủ công thêm.",
        )

    return (
        "genuine",
        5,
        "Không phát hiện dấu hiệu vi phạm bản quyền. Kích hoạt Windows/Office hợp lệ "
        "và khớp với thông tin phần cứng/kênh cấp phép.",
    )
