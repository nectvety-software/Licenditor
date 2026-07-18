"""
tools.py
--------
Các công cụ hệ thống: dọn dẹp temp, gỡ phần mềm, xóa file cứng đầu, quét virus.
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
import glob
from dataclasses import dataclass, field
from typing import Any

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import winreg
else:
    winreg = None


def _run(cmd, shell=False, timeout=60):
    """Chạy lệnh hệ thống an toàn."""
    creationflags = 0
    startupinfo = None
    if IS_WINDOWS:
        creationflags = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    try:
        out = subprocess.check_output(
            cmd, shell=shell, stderr=subprocess.STDOUT, timeout=timeout,
            creationflags=creationflags, startupinfo=startupinfo,
        )
        return True, out.decode("utf-8", errors="ignore")
    except Exception as exc:
        return False, str(exc)


# --------------------------------------------------------------------------- #
# 1) Temp Cleaner - Dọn dẹp file tạm
# --------------------------------------------------------------------------- #

def get_temp_locations() -> list[dict]:
    """Liệt kê các thư mục temp trên hệ thống."""
    locations = []

    temp_dirs = [
        ("Windows Temp", os.environ.get("WINDIR", r"C:\Windows") + r"\Temp"),
        ("User Temp", os.environ.get("TEMP", "")),
        ("Local AppData Temp", os.environ.get("LOCALAPPDATA", "") + r"\Temp"),
        ("Windows Prefetch", os.environ.get("WINDIR", r"C:\Windows") + r"\Prefetch"),
        ("Windows SoftwareDistribution", os.environ.get("WINDIR", r"C:\Windows") + r"\SoftwareDistribution\Download"),
        ("Windows Installer Cache", os.environ.get("WINDIR", r"C:\Windows") + r"\Installer\$PatchCache$"),
        ("Windows Logs", os.environ.get("WINDIR", r"C:\Windows") + r"\Logs"),
        ("Windows Minidump", os.environ.get("WINDIR", r"C:\Windows") + r"\Minidump"),
        ("Windows Temp Internet", os.environ.get("LOCALAPPDATA", "") + r"\Microsoft\Windows\INetCache"),
    ]

    for name, path in temp_dirs:
        if not path or not os.path.isdir(path):
            continue
        try:
            total_size = 0
            file_count = 0
            for entry in os.scandir(path):
                if entry.is_file():
                    try:
                        total_size += entry.stat().st_size
                        file_count += 1
                    except (OSError, PermissionError):
                        pass
            locations.append({
                "name": name,
                "path": path,
                "size_bytes": total_size,
                "file_count": file_count,
            })
        except (OSError, PermissionError):
            pass

    return locations


def clean_temp_folder(path: str) -> dict:
    """Xóa file tạm trong thư mục, giữ lại thư mục gốc."""
    deleted = 0
    freed = 0
    errors = []

    if not os.path.isdir(path):
        return {"deleted": 0, "freed": 0, "errors": ["Thư mục không tồn tại"]}

    for entry in os.scandir(path):
        try:
            if entry.is_file():
                size = entry.stat().st_size
                os.unlink(entry.path)
                deleted += 1
                freed += size
            elif entry.is_dir() and entry.name.lower() not in ("desktop.ini",):
                shutil.rmtree(entry.path, ignore_errors=True)
                deleted += 1
        except (OSError, PermissionError) as exc:
            errors.append(f"{entry.name}: {exc}")

    return {"deleted": deleted, "freed": freed, "errors": errors}


# --------------------------------------------------------------------------- #
# 2) Uninstaller - Gỡ bỏ phần mềm
# --------------------------------------------------------------------------- #

def list_installed_programs() -> list[dict]:
    """Liệt kê chương trình đã cài từ registry."""
    programs = []
    uninstall_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for hive, path in uninstall_paths:
        try:
            with winreg.OpenKey(hive, path) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            try:
                                display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                if not display_name or len(display_name) < 2:
                                    i += 1
                                    continue
                                try:
                                    display_version, _ = winreg.QueryValueEx(subkey, "DisplayVersion")
                                except FileNotFoundError:
                                    display_version = ""
                                try:
                                    publisher, _ = winreg.QueryValueEx(subkey, "Publisher")
                                except FileNotFoundError:
                                    publisher = ""
                                try:
                                    uninstall_string, _ = winreg.QueryValueEx(subkey, "UninstallString")
                                except FileNotFoundError:
                                    uninstall_string = ""
                                try:
                                    install_location, _ = winreg.QueryValueEx(subkey, "InstallLocation")
                                except FileNotFoundError:
                                    install_location = ""
                                try:
                                    estimated_size, _ = winreg.QueryValueEx(subkey, "EstimatedSize")
                                except FileNotFoundError:
                                    estimated_size = 0

                                programs.append({
                                    "name": display_name,
                                    "version": display_version,
                                    "publisher": publisher,
                                    "uninstall_string": uninstall_string,
                                    "install_location": install_location,
                                    "size_kb": estimated_size,
                                    "registry_key": f"{path}\\{subkey_name}",
                                })
                            except FileNotFoundError:
                                pass
                        i += 1
                    except OSError:
                        break
        except (FileNotFoundError, PermissionError):
            continue

    programs.sort(key=lambda x: x["name"].lower())
    return programs


def uninstall_program(program: dict) -> dict:
    """Gỡ bỏ chương trình bằng lệnh uninstall."""
    uninstall_cmd = program.get("uninstall_string", "")
    if not uninstall_cmd:
        return {"success": False, "error": "Không tìm thấy lệnh gỡ bỏ."}

    if uninstall_cmd.startswith('"'):
        parts = uninstall_cmd.split('"', 2)
        cmd_path = parts[1] if len(parts) > 1 else uninstall_cmd
        cmd_args = parts[2].strip() if len(parts) > 2 else ""
    else:
        parts = uninstall_cmd.split(" ", 1)
        cmd_path = parts[0]
        cmd_args = parts[1] if len(parts) > 1 else ""

    if cmd_path.lower().endswith(".exe"):
        ok, output = _run(f'"{cmd_path}" /S', shell=True, timeout=120)
        if ok:
            return {"success": True, "output": "Đã gỡ bỏ thành công."}
        ok2, output2 = _run(f'"{cmd_path}"', shell=True, timeout=120)
        if ok2:
            return {"success": True, "output": "Đã mở trình gỡ bỏ."}
        return {"success": False, "error": output or output2}
    elif cmd_path.lower().endswith(".msi"):
        ok, output = _run(f'msiexec /x "{cmd_path}" /quiet /norestart', shell=True, timeout=120)
        return {"success": ok, "output": output if ok else f"Lỗi: {output}"}

    return {"success": False, "error": f"Không hỗ trợ loại lệnh: {uninstall_cmd}"}


def _normalize_name(name: str) -> str:
    """Chuẩn hóa tên phần mềm để dùng làm tên thư mục/quét registry."""
    n = name.strip().lower()
    for ch in "():/\\!@#$%^&*+=<>?\"|~`":
        n = n.replace(ch, "")
    n = n.replace(" ", "").replace("-", "").replace("_", "").replace(".", "")
    return n


def _find_leftover_paths(program_name: str, install_location: str = "") -> list[dict]:
    """Tìm thư mục/file sót lại của phần mềm sau khi gỡ."""
    leftovers = []
    name_normalized = _normalize_name(program_name)
    name_variants = {name_normalized, program_name.strip().lower().replace(" ", "")}

    base_dirs = [
        ("Local AppData", os.environ.get("LOCALAPPDATA", "")),
        ("Roaming AppData", os.environ.get("APPDATA", "")),
        ("ProgramData", os.environ.get("PROGRAMDATA", r"C:\ProgramData")),
        ("User Documents", os.environ.get("USERPROFILE", "") + r"\Documents"),
        ("User Home", os.environ.get("USERPROFILE", "")),
    ]

    if install_location and os.path.isdir(install_location):
        leftovers.append({
            "type": "folder",
            "source": "Install location",
            "path": install_location,
            "size": _get_dir_size(install_location),
        })

    for label, base in base_dirs:
        if not base or not os.path.isdir(base):
            continue
        try:
            for entry in os.scandir(base):
                entry_lower = entry.name.lower().replace(" ", "").replace("-", "").replace("_", "").replace(".", "")
                for variant in name_variants:
                    if variant in entry_lower or entry_lower in variant:
                        if entry.is_dir():
                            leftovers.append({
                                "type": "folder",
                                "source": label,
                                "path": entry.path,
                                "size": _get_dir_size(entry.path),
                            })
                        break
        except (OSError, PermissionError):
            pass

    return leftovers


def _get_dir_size(path: str) -> int:
    """Tính tổng dung lượng thư mục."""
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                try:
                    fp = os.path.join(dirpath, f)
                    total += os.path.getsize(fp)
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total


def _find_leftover_registry(program_name: str) -> list[dict]:
    """Tìm key registry sót lại của phần mềm."""
    leftovers = []
    name_normalized = _normalize_name(program_name)
    name_lower = program_name.strip().lower()

    reg_paths = [
        (winreg.HKEY_CURRENT_USER, r"Software"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    seen = set()
    for hive, reg_path in reg_paths:
        try:
            with winreg.OpenKey(hive, reg_path) as key:
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey_lower = subkey_name.lower().replace(" ", "").replace("-", "").replace("_", "")
                        if name_normalized in subkey_lower or name_lower.replace(" ", "") in subkey_lower:
                            full_path = f"{reg_path}\\{subkey_name}"
                            if full_path not in seen:
                                seen.add(full_path)
                                leftovers.append({
                                    "type": "registry",
                                    "source": f"HKEY_CURRENT_USER\\{reg_path}" if hive == winreg.HKEY_CURRENT_USER else f"HKEY_LOCAL_MACHINE\\{reg_path}",
                                    "path": full_path,
                                    "hive": hive,
                                })
                        i += 1
                    except OSError:
                        break
        except (OSError, PermissionError):
            pass

    return leftovers


def scan_leftovers(program: dict) -> list[dict]:
    """Quét toàn bộ dữ liệu sót lại của phần mềm (file + registry)."""
    name = program.get("name", "")
    install_loc = program.get("install_location", "")
    leftovers = _find_leftover_paths(name, install_loc)
    leftovers.extend(_find_leftover_registry(name))
    return leftovers


def clean_leftover(leftover: dict) -> dict:
    """Xóa một mục leftover (thư mục hoặc registry)."""
    if leftover["type"] == "folder":
        path = leftover["path"]
        if not os.path.exists(path):
            return {"success": False, "error": "Không tồn tại."}
        try:
            _run(f'takeown /F "{path}" /R /D Y 2>nul', shell=True, timeout=30)
            _run(f'icacls "{path}" /grant Everyone:F /T /Q 2>nul', shell=True, timeout=30)
            shutil.rmtree(path, ignore_errors=True)
            if not os.path.exists(path):
                return {"success": True, "output": f"Đã xóa: {path}"}
            _run(f'rmdir /S /Q "{path}"', shell=True, timeout=30)
            if not os.path.exists(path):
                return {"success": True, "output": f"Đã xóa (force): {path}"}
            return {"success": False, "error": "Không thể xóa thư mục."}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    elif leftover["type"] == "registry":
        try:
            hive = leftover.get("hive", winreg.HKEY_CURRENT_USER)
            path = leftover["path"]
            separator = path.index("\\")
            base_path = path[separator + 1:]
            with winreg.OpenKey(hive, "", 0, winreg.KEY_ALL_ACCESS) as key:
                try:
                    winreg.DeleteKey(key, base_path)
                    return {"success": True, "output": f"Đã xóa registry: {path}"}
                except FileNotFoundError:
                    return {"success": True, "output": f"Registry đã được xóa trước: {path}"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    return {"success": False, "error": "Loại không hỗ trợ."}


def clean_all_leftovers(program_name: str, leftovers: list[dict]) -> dict:
    """Xóa tất cả leftover của phần mềm, trả về kết quả chi tiết."""
    results = {"deleted": 0, "failed": 0, "freed_bytes": 0, "details": []}
    for item in leftovers:
        if item["type"] == "folder":
            size = item.get("size", 0)
        else:
            size = 0
        result = clean_leftover(item)
        if result.get("success"):
            results["deleted"] += 1
            results["freed_bytes"] += size
            results["details"].append(result["output"])
        else:
            results["failed"] += 1
            results["details"].append(f"Lỗi: {result.get('error', '')}")
    return results


def uninstall_and_clean(program: dict) -> dict:
    """Gỡ bỏ phần mềm + quét + xóa leftover sạch sẽ."""
    result = {"uninstall": {}, "leftovers": [], "leftover_results": {}}
    name = program.get("name", "")

    result["uninstall"] = uninstall_program(program)

    leftovers = scan_leftovers(program)
    result["leftovers"] = leftovers

    if leftovers:
        result["leftover_results"] = clean_all_leftovers(name, leftovers)

    return result


def _get_installed_names_set() -> set:
    """Lấy set tên + publisher đã chuẩn hóa của tất cả phần mềm đang cài."""
    names = set()
    for prog in list_installed_programs():
        n = _normalize_name(prog.get("name", ""))
        if n:
            names.add(n)
        p = _normalize_name(prog.get("publisher", ""))
        if p:
            names.add(p)
    return names


def scan_orphaned_appdata() -> list[dict]:
    """Quét thư mục AppData/ProgramData còn sót từ phần mềm đã gỡ."""
    leftovers = []
    installed_normalized = _get_installed_names_set()

    scan_dirs = [
        ("Local AppData", os.environ.get("LOCALAPPDATA", "")),
        ("Roaming AppData", os.environ.get("APPDATA", "")),
        ("ProgramData", os.environ.get("PROGRAMDATA", r"C:\ProgramData")),
        ("User Temp", os.environ.get("TEMP", "")),
    ]

    safe_names = {
        "microsoft", "windows", "microsoftshared", "microsoft.net",
        "assembly", "temp", "tmp", "cache", "cached", "logs", "log",
        "appdata", "local", "locallow", "roaming", "programdata",
        "google", "chrome", "edge", "firefox", "mozilla", "opera",
        "adobe", "oracle", "java", "javasoft", "sun", "mysql",
        "npm", "pip", "nuget", "chocolatey", "scoop", "winget",
        "intel", "amd", "nvidia", "ati", "realtek",
        "common files", "installer", "{", "crashpad", "spotify",
        "discord", "telegram", "slack", "teams", "zoom",
        "dropbox", "onedrive", "googledrive", "icloud",
        "python", "nodejs", "ruby", "go", "rust", "dotnet",
        "git", "svn", "mercurial", "vscode", "visualstudio",
        "docker", "kubernetes", "vmware", "virtualbox",
        "winrar", "7zip", "winzip", "bandizip",
        "vlc", "mpc", "potplayer", "kmplayer",
        "libreoffice", "openoffice", "wps office",
        "notepad++", "notepadpp", "sublime", "atom",
        "steam", "epic", "gog", "origin", "ubisoft",
        "cmake", "mingw", "cygwin", "wsl",
        "cert", "crl", "temp", "tmp", "appdata",
    }

    for label, base in scan_dirs:
        if not base or not os.path.isdir(base):
            continue
        try:
            for entry in os.scandir(base):
                if not entry.is_dir():
                    continue
                name = entry.name
                name_norm = _normalize_name(name)

                if name.startswith(".") or name.startswith("$"):
                    continue
                if name_norm in safe_names:
                    continue
                if any(safe in name_norm for safe in safe_names if len(safe) > 3):
                    continue
                if len(name_norm) < 2:
                    continue

                matched = False
                for installed in installed_normalized:
                    if not installed:
                        continue
                    if name_norm == installed or name_norm in installed or installed in name_norm:
                        matched = True
                        break

                if not matched:
                    leftovers.append({
                        "name": name,
                        "path": entry.path,
                        "source": label,
                        "size_bytes": 0,
                        "file_count": 0,
                    })
        except (OSError, PermissionError):
            pass

    # Tính kích thước nhanh (giới hạn depth=2, tối đa 5000 file)
    for item in leftovers:
        try:
            size = 0
            count = 0
            for dirpath, _, filenames in os.walk(item["path"]):
                depth = dirpath[len(item["path"]):].count(os.sep)
                if depth > 2 or count > 5000:
                    break
                for f in filenames:
                    if count > 5000:
                        break
                    try:
                        size += os.path.getsize(os.path.join(dirpath, f))
                        count += 1
                    except (OSError, PermissionError):
                        pass
            if count > 5000:
                item["file_count"] = count
                item["size_bytes"] = size
                item["warning"] = "Nhi\u1ec1u file, dung l\u01b0\u1ee3ng c\u00f3 th\u1ec3 l\u1edbn h\u01a1n"
            else:
                item["size_bytes"] = size
                item["file_count"] = count
        except (OSError, PermissionError):
            pass

    leftovers.sort(key=lambda x: x["size_bytes"], reverse=True)
    return leftovers


# --------------------------------------------------------------------------- #
# 3) Xóa file/thư mục cứng đầu
# --------------------------------------------------------------------------- #

def force_delete(path: str) -> dict:
    """Xóa file/thư mục cứng đầu bằng cách thay đổi quyền trước khi xóa."""
    if not os.path.exists(path):
        return {"success": False, "error": "Đường dẫn không tồn tại."}

    try:
        if IS_WINDOWS:
            _run(f'takeown /F "{path}" /R /D Y', shell=True, timeout=30)
            _run(f'icacls "{path}" /grant Everyone:F /T /Q', shell=True, timeout=30)

        if os.path.isfile(path):
            os.unlink(path)
            return {"success": True, "output": f"Đã xóa file: {path}"}
        elif os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=False)
            return {"success": True, "output": f"Đã xóa thư mục: {path}"}
    except Exception as exc:
        pass

    try:
        if os.path.isfile(path):
            _run(f'cmd /c del /F /Q "{path}"', shell=True, timeout=30)
        elif os.path.isdir(path):
            _run(f'cmd /c rmdir /S /Q "{path}"', shell=True, timeout=60)

        if not os.path.exists(path):
            return {"success": True, "output": f"Đã xóa bằng cmd: {path}"}
        else:
            return {"success": False, "error": "Không thể xóa. Có thể file đang bị sử dụng."}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def scan_locked_files(directory: str, max_depth: int = 3) -> list[dict]:
    """Quét các file/thư mục có thể bị khóa hoặc không thể xóa bình thường."""
    locked_items = []

    if not os.path.isdir(directory):
        return locked_items

    base_depth = directory.rstrip(os.sep).count(os.sep)

    for dirpath, dirnames, filenames in os.walk(directory):
        depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
        if depth >= max_depth:
            dirnames[:] = []
            continue

        for name in filenames:
            filepath = os.path.join(dirpath, name)
            try:
                stat = os.stat(filepath)
                if stat.st_size == 0:
                    locked_items.append({"path": filepath, "reason": "File rỗng (0 bytes)", "size": 0})
            except (OSError, PermissionError):
                locked_items.append({"path": filepath, "reason": "Không thể truy cập", "size": -1})

        for name in dirnames:
            dirpath_full = os.path.join(dirpath, name)
            try:
                os.listdir(dirpath_full)
            except (OSError, PermissionError):
                locked_items.append({"path": dirpath_full, "reason": "Thư mục không thể truy cập", "size": -1})

    return locked_items


# --------------------------------------------------------------------------- #
# 4) Quét virus - Kiểm tra hệ thống
# --------------------------------------------------------------------------- #

def scan_with_windows_defender() -> dict:
    """Quét hệ thống bằng Windows Defender (PowerShell MpCmdRun)."""
    cmd = (
        "(Get-MpThreatDetection | Select-Object -First 20) | "
        "ForEach-Object { "
        "$detection = $_; "
        "$threat = Get-MpThreat -ThreatID $detection.ThreatID -ErrorAction SilentlyContinue; "
        "[PSCustomObject]@{"
        "ThreatName=$threat.ThreatName; "
        "DetectionTime=$detection.InitialDetectionTime; "
        "ActionSuccess=$detection.ActionSuccess; "
        "Resources=$detection.Resources[0]; "
        "Severity=$detection.ThreatStatusID"
        "} } | ConvertTo-Json -Depth 3"
    )

    ok, output = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
        timeout=60,
    )

    if not ok or not output.strip():
        return {"threats": [], "message": "Không phát hiện mối đe dọa hoặc Windows Defender chưa hoạt động."}

    import json
    try:
        threats = json.loads(output)
        if isinstance(threats, dict):
            threats = [threats]
    except json.JSONDecodeError:
        threats = []

    return {"threats": threats, "message": f"Phát hiện {len(threats)} mối đe dọa."}


def scan_quick_defender() -> dict:
    """Quét nhanh bằng Windows Defender."""
    ok, output = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "Start-MpScan -ScanType QuickScan | Select-Object -Property Resources,Started,Completed | ConvertTo-Json"],
        timeout=120,
    )

    if ok:
        return {"success": True, "output": "Quét nhanh hoàn tất."}
    return {"success": False, "output": output}


# --------------------------------------------------------------------------- #
# 5) Thẻ nhớ - Khôi phục / Sửa chữa
# --------------------------------------------------------------------------- #

def detect_removable_drives() -> list[dict]:
    """Phát hiện các ổ đĩa di động (USB, thẻ nhớ) đang kết nối."""
    if not IS_WINDOWS:
        return []

    drives = []
    ok, output = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "Get-Volume | Where-Object { $_.DriveType -eq 'Removable' -or $_.DriveLetter } | "
         "Select-Object DriveLetter,FileSystemLabel,FileSystem,Size,SizeRemaining,HealthStatus | "
         "ConvertTo-Json -Depth 3"],
        timeout=15,
    )

    if not ok or not output.strip():
        return []

    import json
    try:
        volumes = json.loads(output)
        if isinstance(volumes, dict):
            volumes = [volumes]
        for v in volumes:
            letter = v.get("DriveLetter", "")
            if not letter:
                continue
            drives.append({
                "letter": letter,
                "label": v.get("FileSystemLabel", ""),
                "filesystem": v.get("FileSystem", ""),
                "total_bytes": v.get("Size", 0),
                "free_bytes": v.get("SizeRemaining", 0),
                "health": v.get("HealthStatus", "Unknown"),
                "path": f"{letter}:\\",
            })
    except json.JSONDecodeError:
        pass

    return drives


def check_disk_health(drive_letter: str) -> dict:
    """Kiểm tra sức khỏe ổ đĩa bằng WMIC và chkdsk."""
    result = {
        "drive": drive_letter,
        "status": "unknown",
        "details": [],
    }

    ok, output = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         f"Get-Volume -DriveLetter {drive_letter} | Select-Object HealthStatus,SizeRemaining,Size | ConvertTo-Json"],
        timeout=15,
    )

    if ok and output.strip():
        import json
        try:
            vol = json.loads(output)
            result["health"] = vol.get("HealthStatus", "Unknown")
            result["total"] = vol.get("Size", 0)
            result["free"] = vol.get("SizeRemaining", 0)
        except json.JSONDecodeError:
            pass

    ok2, chkdsk_out = _run(
        f"chkdsk {drive_letter}: /F /X",
        shell=True,
        timeout=60,
    )
    result["chkdsk_output"] = chkdsk_out if ok2 else "Không thể chạy chkdsk"

    return result


def format_drive(drive_letter: str, filesystem: str = "NTFS", quick: bool = True) -> dict:
    """Format ổ đĩa (CẢNH BÁO: xóa toàn bộ dữ liệu)."""
    flag = "/Q" if quick else ""
    ok, output = _run(
        f"format {drive_letter}: /FS:{filesystem} {flag} /Y",
        shell=True,
        timeout=300,
    )
    return {"success": ok, "output": output}


def recover_deleted_files(drive_path: str) -> dict:
    """Quét phục hồi file đã xóa bằng PowerShell / undelete tools."""
    ok, output = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         f"Get-ChildItem -Path '{drive_path}' -Recurse -Force -ErrorAction SilentlyContinue | "
         f"Where-Object {{ $_.Attributes -band [IO.FileAttributes]::Hidden }} | "
         f"Select-Object FullName,Length,LastWriteTime | ConvertTo-Json -Depth 3"],
        timeout=30,
    )

    files = []
    if ok and output.strip():
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            files = data
        except json.JSONDecodeError:
            pass

    return {"hidden_files": files, "count": len(files)}


def get_disk_info(drive_letter: str) -> dict:
    """Lấy thông tin chi tiết ổ đĩa từ disk vật lý."""
    import json
    result = {
        "drive": drive_letter,
        "disk_number": -1,
        "friendly_name": "",
        "bus_type": "",
        "size_bytes": 0,
        "is_boot": False,
        "is_system": False,
        "is_readonly": False,
        "is_offline": False,
        "partition_count": 0,
        "partition_style": "",
        "filesystem": "",
        "health": "",
    }

    ps = f"""
$ErrorActionPreference = 'SilentlyContinue'
$p = Get-Partition -DriveLetter '{drive_letter}' -ErrorAction SilentlyContinue
$d = Get-Disk -Number $p.DiskNumber -ErrorAction SilentlyContinue
$v = Get-Volume -DriveLetter '{drive_letter}' -ErrorAction SilentlyContinue
$parts = @(Get-Partition -DiskNumber $d.Number -ErrorAction SilentlyContinue)

[pscustomobject]@{{
  DriveLetter     = '{drive_letter}'
  DiskNumber      = [int]$d.Number
  FriendlyName    = [string]$d.FriendlyName
  BusType         = [string]$d.BusType
  SizeBytes       = [int64]$d.Size
  IsBoot          = [bool]$d.IsBoot
  IsSystem        = [bool]$d.IsSystem
  IsReadOnly      = [bool]$d.IsReadOnly
  IsOffline       = [bool]$d.IsOffline
  PartitionCount  = [int]$parts.Count
  PartitionStyle  = [string]$d.PartitionStyle
  FileSystem      = if ($null -ne $v) {{ [string]$v.FileSystem }} else {{ '' }}
  HealthStatus    = if ($null -ne $v) {{ [string]$v.HealthStatus }} else {{ '' }}
}} | ConvertTo-Json -Compress
"""
    ok, output = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", ps],
        timeout=15,
    )

    if ok and output.strip():
        try:
            data = json.loads(output)
            result["disk_number"] = data.get("DiskNumber", -1)
            result["friendly_name"] = data.get("FriendlyName", "")
            result["bus_type"] = data.get("BusType", "")
            result["size_bytes"] = data.get("SizeBytes", 0)
            result["is_boot"] = data.get("IsBoot", False)
            result["is_system"] = data.get("IsSystem", False)
            result["is_readonly"] = data.get("IsReadOnly", False)
            result["is_offline"] = data.get("IsOffline", False)
            result["partition_count"] = data.get("PartitionCount", 0)
            result["partition_style"] = data.get("PartitionStyle", "")
            result["filesystem"] = data.get("FileSystem", "")
            result["health"] = data.get("HealthStatus", "")
        except json.JSONDecodeError:
            pass

    return result


def check_capacity_sanity(drive_letter: str, expected_gb: float = 4.0) -> dict:
    """
    Kiểm tra dung lượng có hợp lý không.
    Phát hiện thẻ nhớ giả/hỏng khi Windows báo sai dung lượng.
    """
    info = get_disk_info(drive_letter)
    size_bytes = info.get("size_bytes", 0)
    size_gb = size_bytes / 1_000_000_000

    tolerance = 0.5
    min_gb = expected_gb - tolerance
    max_gb = expected_gb + tolerance + 1.0

    is_plausible = min_gb <= size_gb <= max_gb

    result = {
        "drive": drive_letter,
        "expected_gb": expected_gb,
        "reported_gb": round(size_gb, 2),
        "is_plausible": is_plausible,
        "disk_number": info.get("disk_number", -1),
        "friendly_name": info.get("friendly_name", ""),
        "bus_type": info.get("bus_type", ""),
        "is_boot": info.get("is_boot", False),
        "is_system": info.get("is_system", False),
        "issues": [],
        "recommendations": [],
    }

    if info.get("is_boot") or info.get("is_system"):
        result["issues"].append("THẺ NÀY LÀ Ổ BOOT/SYSTEM - KHÔNG ĐƯỢC FORMAT!")
        result["recommendations"].append("Đây là ổ cài Windows, không phải thẻ nhớ")

    if info.get("disk_number") == 0:
        result["issues"].append("Disk 0 thường là ổ cài Windows - KHÔNGFormat!")
        result["recommendations"].append("Kiểm tra lại trong Disk Management")

    if not is_plausible:
        result["issues"].append(
            f"NGHIÊM TRỌNG: Thẻ {expected_gb:.0f}GB đang báo {size_gb:.2f}GB"
        )
        if size_gb > 100:
            result["issues"].append(
                "Dung lượng bất thường (>100GB cho thẻ nhỏ) - Thẻ giả hoặc đầu đọc lỗi!"
            )
            result["recommendations"].append("Thẻ nhớ có thể là giả (fake capacity)")
            result["recommendations"].append("Đổi đầu đọc/adapter khác")
            result["recommendations"].append("Thử trên máy tính khác")
            result["recommendations"].append("KHÔNG format - có thể mất dữ liệu")
        else:
            result["issues"].append("Dung lượng không khớp với kỳ vọng")
            result["recommendations"].append("Thẻ có thể bị hỏng hoặc controller lỗi")

    if info.get("is_readonly"):
        result["issues"].append("Ổ đĩa đang ở chế độ read-only")

    if info.get("partition_count", 0) > 1:
        result["issues"].append(f"Có {info['partition_count']} phân vùng (thường chỉ có 1)")

    if not result["issues"]:
        result["issues"].append("Dung lượng hợp lý")
        result["recommendations"].append("Có thể an toàn format")

    return result


def diagnose_drive(drive_letter: str) -> dict:
    """Chẩn đoán chi tiết tình trạng ổ đĩa: RAW, read-only, capacity, v.v."""
    result = {
        "drive": drive_letter,
        "is_raw": False,
        "is_readonly": False,
        "is_accessible": False,
        "filesystem": "",
        "health": "Unknown",
        "total_bytes": 0,
        "free_bytes": 0,
        "disk_info": {},
        "capacity_check": {},
        "issues": [],
        "recommendations": [],
    }

    disk_info = get_disk_info(drive_letter)
    result["disk_info"] = disk_info
    result["total_bytes"] = disk_info.get("size_bytes", 0)
    result["filesystem"] = disk_info.get("filesystem", "") or "RAW"
    result["health"] = disk_info.get("health", "Unknown")
    result["is_readonly"] = disk_info.get("is_readonly", False)

    cap_check = check_capacity_sanity(drive_letter)
    result["capacity_check"] = cap_check

    if not disk_info.get("filesystem") or disk_info.get("filesystem", "").upper() == "RAW":
        result["is_raw"] = True
        result["issues"].append("Ổ đĩa ở trạng thái RAW (không có file system)")
        result["recommendations"].append("Cần format ổ đĩa để sử dụng được")

    result["issues"].extend(cap_check.get("issues", []))
    result["recommendations"].extend(cap_check.get("recommendations", []))

    if not result["issues"]:
        result["issues"].append("Không phát hiện vấn đề")
        result["recommendations"].append("Ổ đĩa hoạt động bình thường")

    return result


def fix_readonly(drive_letter: str) -> dict:
    """Tắt chế độ read-only của ổ đĩa."""
    ok, output = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         f"$disk = Get-Disk | Where-Object {{ $_.Number -eq (Get-Partition -DriveLetter {drive_letter}).DiskNumber }}; "
         f"if ($disk.IsReadOnly) {{ $disk | Set-Disk -IsReadOnly $false; 'Da tat read-only' }} "
         f"else {{ 'Read-only da tat hoac khong ap dung' }}"],
        timeout=15,
    )
    return {"success": ok, "output": output.strip() if ok else output}


def set_disk_online(drive_letter: str) -> dict:
    """Set ổ đĩa online nếu đang offline."""
    ok, output = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         f"$disk = Get-Disk | Where-Object {{ $_.Number -eq (Get-Partition -DriveLetter {drive_letter}).DiskNumber }}; "
         f"if ($disk.IsOffline) {{ $disk | Set-Disk -IsOffline $false; 'Da set online' }} "
         f"else {{ 'O dia da online hoac khong tim thay' }}"],
        timeout=15,
    )
    return {"success": ok, "output": output.strip() if ok else output}


def safe_format(drive_letter: str, filesystem: str = "exFAT", label: str = "USB_DRIVE") -> dict:
    """Format an toàn với kiểm tra dung lượng và xử lý lỗi chi tiết."""
    issues = []

    cap_check = check_capacity_sanity(drive_letter)
    if not cap_check.get("is_plausible"):
        reported = cap_check.get("reported_gb", 0)
        expected = cap_check.get("expected_gb", 4)
        issues.append(f"CẢNH BÁO: Thẻ {expected:.0f}GB báo {reported}GB - Thẻ giả hoặc đầu đọc lỗi!")
        issues.append("TỪ CHỐI format để bảo vệ dữ liệu")
        return {
            "success": False,
            "output": f"Thẻ {expected:.0f}GB báo sai dung lượng ({reported}GB). Không format.",
            "issues": issues,
            "capacity_error": True,
        }

    if cap_check.get("is_boot") or cap_check.get("is_system"):
        issues.append("TỪ CHỐI: Đây là ổ Boot/System!")
        return {"success": False, "output": "Không format được ổ Boot/System", "issues": issues}

    if cap_check.get("disk_number") == 0:
        issues.append("TỪ CHỐI: Disk 0 thường là ổ cài Windows!")
        return {"success": False, "output": "Không format được Disk 0", "issues": issues}

    diag = diagnose_drive(drive_letter)
    if diag.get("is_readonly"):
        fix_result = fix_readonly(drive_letter)
        issues.append(f"Tắt read-only: {fix_result.get('output', '')}")

    if diag.get("is_raw"):
        issues.append("Ổ đĩa RAW - cần format để sử dụng")

    ok, output = _run(
        f"format {drive_letter}: /FS:{filesystem} /V:{label} /Q /Y",
        shell=True,
        timeout=300,
    )

    if ok:
        return {"success": True, "output": output, "issues": issues}

    issues.append(f"Format thường thất bại: {output[:200]}")

    issues.append("Thử dùng diskpart để format...")
    disk_num = _get_disk_number(drive_letter)
    if disk_num:
        dp_result = _diskpart_format(disk_num, filesystem, label)
        issues.extend(dp_result.get("issues", []))
        if dp_result.get("success"):
            return {"success": True, "output": dp_result.get("output", ""), "issues": issues}

    return {"success": False, "output": output, "issues": issues}


def _get_disk_number(drive_letter: str) -> str:
    """Lấy số ổ đĩa từ letter."""
    ok, output = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         f"Get-Partition -DriveLetter {drive_letter} | Select-Object -ExpandProperty DiskNumber"],
        timeout=10,
    )
    if ok and output.strip():
        return output.strip()
    return ""


def _diskpart_format(disk_number: str, filesystem: str, label: str) -> dict:
    """Dùng diskpart để clean và format ổ đĩa."""
    issues = []

    script = f"""select disk {disk_number}
clean
create partition primary
format fs={filesystem} label="{label}" quick
assign
exit"""

    ok, output = _run(
        ["diskpart"],
        shell=True,
        timeout=120,
    )

    if not ok:
        try:
            proc = subprocess.Popen(
                ["diskpart"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
            )
            stdout, _ = proc.communicate(input=script, timeout=120)
            output = stdout
            ok = proc.returncode == 0
        except Exception as exc:
            return {"success": False, "output": str(exc), "issues": [f"Lỗi chạy diskpart: {exc}"]}

    if ok:
        issues.append("Đã dùng diskpart clean và format lại")
    else:
        issues.append(f"diskpart thất bại: {output[:200]}")

    return {"success": ok, "output": output, "issues": issues}


def force_format(drive_letter: str, filesystem: str = "exFAT", label: str = "USB_DRIVE") -> dict:
    """Bắt buộc format bằng diskpart với kiểm tra dung lượng an toàn."""
    issues = []

    cap_check = check_capacity_sanity(drive_letter)
    if not cap_check.get("is_plausible"):
        reported = cap_check.get("reported_gb", 0)
        expected = cap_check.get("expected_gb", 4)
        issues.append(f"CẢNH BÁO: Thẻ {expected:.0f}GB báo {reported}GB - Thẻ giả hoặc đầu đọc lỗi!")
        issues.append("TỪ CHỐI format để bảo vệ dữ liệu")
        return {
            "success": False,
            "output": f"Thẻ {expected:.0f}GB báo sai dung lượng ({reported}GB). Không format.",
            "issues": issues,
            "capacity_error": True,
        }

    if cap_check.get("is_boot") or cap_check.get("is_system"):
        issues.append("TỪ CHỐI: Đây là ổ Boot/System!")
        return {"success": False, "output": "Không format được ổ Boot/System", "issues": issues}

    if cap_check.get("disk_number") == 0:
        issues.append("TỪ CHỐI: Disk 0 thường là ổ cài Windows!")
        return {"success": False, "output": "Không format được Disk 0", "issues": issues}

    fix_readonly(drive_letter)
    issues.append("Đã thử tắt read-only")

    disk_num = _get_disk_number(drive_letter)
    if not disk_num:
        return {"success": False, "output": "Không tìm thấy số ổ đĩa", "issues": issues}

    issues.append(f"Số ổ đĩa: {disk_num}")

    script = f"""select disk {disk_num}
attributes disk clear readonly
online disk noerr
clean
convert mbr
create partition primary
format fs={filesystem} label="{label}" quick
assign letter={drive_letter}
exit"""

    try:
        proc = subprocess.Popen(
            ["diskpart"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
        )
        stdout, _ = proc.communicate(input=script, timeout=120)
        ok = proc.returncode == 0
        issues.append("Đã chạy diskpart clean + format")
        return {"success": ok, "output": stdout, "issues": issues}
    except Exception as exc:
        return {"success": False, "output": str(exc), "issues": issues + [f"Lỗi: {exc}"]}


def repair_filesystem(drive_letter: str) -> dict:
    """Sửa chữa filesystem bằng chkdsk /R với xử lý lỗi chi tiết."""
    issues = []

    diag = diagnose_drive(drive_letter)
    if diag.get("is_raw"):
        return {
            "success": False,
            "output": "Ổ đĩa RAW - không thể chạy chkdsk. Cần format lại.",
            "issues": ["Ổ đĩa ở trạng thái RAW"],
            "recommendation": "Sử dụng tính năng 'Format an toàn' để修复",
        }

    if diag.get("is_readonly"):
        fix_result = fix_readonly(drive_letter)
        issues.append(f"Đã tắt read-only: {fix_result.get('output', '')}")

    ok, output = _run(
        f"chkdsk {drive_letter}: /R /F",
        shell=True,
        timeout=180,
    )

    if not ok and "read-only" in output.lower():
        issues.append("Ổ đĩa đang read-only, thử tắt...")
        fix_readonly(drive_letter)
        ok2, output2 = _run(
            f"chkdsk {drive_letter}: /R /F",
            shell=True,
            timeout=180,
        )
        return {
            "success": ok2,
            "output": output2,
            "issues": issues,
        }

    return {"success": ok, "output": output, "issues": issues}


def scan_bad_sectors(drive_letter: str) -> dict:
    """Quét bad sectors bằng chkdsk /R."""
    ok, output = _run(
        f"chkdsk {drive_letter}: /R",
        shell=True,
        timeout=300,
    )

    bad_sectors = 0
    if ok and output:
        import re
        m = re.search(r"(\d+)\s+bad\s+sector", output, re.IGNORECASE)
        if m:
            bad_sectors = int(m.group(1))

    return {
        "success": ok,
        "output": output,
        "bad_sectors": bad_sectors,
        "has_bad_sectors": bad_sectors > 0,
    }


def diskpart_clean(drive_letter: str) -> dict:
    """Dùng diskpart để clean ổ đĩa (XÓA TOÀN BỘ PHÂN VÙNG)."""
    ok, output = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         f"Get-Partition -DriveLetter {drive_letter} | Select-Object DiskNumber | Convert-Json"],
        timeout=10,
    )

    disk_num = ""
    if ok and output.strip():
        import json
        try:
            d = json.loads(output)
            if isinstance(d, list):
                d = d[0] if d else {}
            disk_num = str(d.get("DiskNumber", ""))
        except json.JSONDecodeError:
            pass

    if not disk_num:
        return {"success": False, "output": "Không tìm thấy số ổ đĩa"}

    script = f"select disk {disk_num}\nclean"
    ok2, output2 = _run(
        ["diskpart"],
        shell=True,
        timeout=30,
    )

    return {"success": ok2, "output": output2, "disk_number": disk_num}


# --------------------------------------------------------------------------- #
# 6) Phát hiện cổng kết nối ngoài (PORT)
# --------------------------------------------------------------------------- #

def detect_serial_ports() -> list[dict]:
    """Phát hiện các cổng COM/Serial đang hoạt động."""
    ports = []
    ok, output = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "Get-CimInstance -ClassName Win32_SerialPort | "
         "Select-Object DeviceID,Name,Description,BaudRate,Status | ConvertTo-Json -Depth 3"],
        timeout=15,
    )

    if ok and output.strip():
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            for p in data:
                ports.append({
                    "type": "Serial/COM",
                    "name": p.get("DeviceID", ""),
                    "description": p.get("Description", ""),
                    "baud_rate": p.get("BaudRate", 0),
                    "status": p.get("Status", ""),
                })
        except json.JSONDecodeError:
            pass

    return ports


def detect_usb_devices() -> list[dict]:
    """Phát hiện các thiết bị USB đang kết nối."""
    devices = []
    ok, output = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "Get-CimInstance -ClassName Win32_USBControllerDevice | "
         "ForEach-Object { [wmi]$_.Dependent } | "
         "Select-Object Name,DeviceID,Description,Status | "
         "Where-Object { $_.Name -ne $null } | ConvertTo-Json -Depth 3"],
        timeout=20,
    )

    if ok and output.strip():
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            seen = set()
            for d in data:
                name = d.get("Name", "")
                if not name or name in seen:
                    continue
                seen.add(name)
                devices.append({
                    "type": "USB",
                    "name": name,
                    "device_id": d.get("DeviceID", ""),
                    "description": d.get("Description", ""),
                    "status": d.get("Status", ""),
                })
        except json.JSONDecodeError:
            pass

    return devices


def detect_all_external_ports() -> dict:
    """Phát hiện tất cả cổng kết nối ngoài: USB, Serial, Bluetooth, Network."""
    result = {
        "serial_ports": detect_serial_ports(),
        "usb_devices": detect_usb_devices(),
        "network_adapters": [],
        "bluetooth": [],
    }

    ok, output = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "Get-NetAdapter | Where-Object { $_.ConnectorPresent -eq $true -or $_.InterfaceDescription -like '*Wireless*' } | "
         "Select-Object Name,InterfaceDescription,Status,LinkSpeed,MacAddress | ConvertTo-Json -Depth 3"],
        timeout=15,
    )
    if ok and output.strip():
        import json
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                data = [data]
            for a in data:
                result["network_adapters"].append({
                    "name": a.get("Name", ""),
                    "description": a.get("InterfaceDescription", ""),
                    "status": a.get("Status", ""),
                    "speed": a.get("LinkSpeed", ""),
                    "mac": a.get("MacAddress", ""),
                })
        except json.JSONDecodeError:
            pass

    ok2, bt_out = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName,Status,InstanceId | ConvertTo-Json -Depth 3"],
        timeout=15,
    )
    if ok2 and bt_out.strip():
        import json
        try:
            data = json.loads(bt_out)
            if isinstance(data, dict):
                data = [data]
            for b in data:
                result["bluetooth"].append({
                    "name": b.get("FriendlyName", ""),
                    "status": b.get("Status", ""),
                    "id": b.get("InstanceId", ""),
                })
        except json.JSONDecodeError:
            pass

    return result


# --------------------------------------------------------------------------- #
# 7) C: Drive Cleaner - Xóa thư mục trực tiếp không qua thùng rác
# --------------------------------------------------------------------------- #

PROTECTED_PATHS = [
    r"C:\Windows",
    r"C:\Windows\System32",
    r"C:\Windows\SysWOW64",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\ProgramData",
    r"C:\Users",
    r"C:\Boot",
    r"C:\System Volume Information",
    r"C:\$Recycle.Bin",
    r"C:\Recovery",
    r"C:\Documents and Settings",
    r"C:\$Windows.~WS",
    r"C:\$Windows.~BT",
    r"C:\$WinREAgent",
    r"C:\config.msi",
]


def _is_protected_path(path: str) -> tuple[bool, str]:
    """Kiểm tra xem đường dẫn có nằm trong vùng bảo vệ không."""
    normalized = os.path.normpath(path).lower()
    for protected in PROTECTED_PATHS:
        norm_protected = os.path.normpath(protected).lower()
        if normalized == norm_protected or normalized.startswith(norm_protected + os.sep):
            return True, protected
    root = os.path.splitdrive(normalized)[0] + os.sep
    if normalized == root.lower():
        return True, f"Ổ đĩa gốc ({root})"
    return False, ""


def get_c_drive_cleanable_folders() -> list[dict]:
    """Quét các thư mục rác trên C: có thể dọn dẹp an toàn (không đụng file hệ thống)."""
    locations = []

    windir = os.environ.get("WINDIR", r"C:\Windows")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")

    c_drive_paths = [
        ("Windows Temp", windir + r"\Temp"),
        ("Windows Prefetch", windir + r"\Prefetch"),
        ("SoftwareDistribution Download", windir + r"\SoftwareDistribution\Download"),
        ("Windows Minidump", windir + r"\Minidump"),
        ("Windows Logs (1 ngày)", windir + r"\Logs"),
        ("User Temp", os.environ.get("TEMP", "")),
        ("AppData Local Temp", localappdata + r"\Temp"),
        ("Browser Cache (IE/Edge)", localappdata + r"\Microsoft\Windows\INetCache"),
        ("Browser Cookies", localappdata + r"\Microsoft\Windows\INetCookies"),
        ("Recent Documents", os.environ.get("APPDATA", "") + r"\Microsoft\Windows\Recent"),
        ("Delivery Optimization Files", windir + r"\SoftwareDistribution\DeliveryOptimization"),
        ("Windows Error Reporting", localappdata + r"\Microsoft\Windows\WER\ReportQueue"),
        ("Windows Upgrade Logs", windir + r"\Panther"),
        ("Thumbnail Cache", localappdata + r"\Microsoft\Windows\Explorer"),
        ("D3D Shader Cache", localappdata + r"\D3DSCache"),
        ("Downloaded Installers", windir + r"\Downloaded Program Files"),
        ("Office Click-to-Run Cache", localappdata + r"\Microsoft\Office\16.0\OfficeFileCache"),
    ]

    for name, path in c_drive_paths:
        if not path or not os.path.isdir(path):
            continue
        protected, _ = _is_protected_path(path)
        if protected:
            continue
        try:
            total_size = 0
            file_count = 0
            for entry in os.scandir(path):
                try:
                    if entry.is_file():
                        total_size += entry.stat().st_size
                        file_count += 1
                except (OSError, PermissionError):
                    pass
            locations.append({
                "name": name,
                "path": path,
                "size_bytes": total_size,
                "file_count": file_count,
            })
        except (OSError, PermissionError):
            pass

    locations.sort(key=lambda x: x["size_bytes"], reverse=True)
    return locations


def get_folder_size(folder_path: str) -> dict:
    """Tính tổng dung lượng và số file trong thư mục."""
    total_size = 0
    file_count = 0
    if not os.path.isdir(folder_path):
        return {"size_bytes": 0, "file_count": 0}
    try:
        for dirpath, _, filenames in os.walk(folder_path):
            for f in filenames:
                try:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
                    file_count += 1
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return {"size_bytes": total_size, "file_count": file_count}


def permanent_delete(path: str) -> dict:
    """Xóa vĩnh viễn file/thư mục (không qua thùng rác).
    TỪ CHỐI xóa các thư mục hệ thống quan trọng."""
    if not os.path.exists(path):
        return {"success": False, "error": "Đường dẫn không tồn tại."}

    protected_name, _ = _is_protected_path(path)
    if protected_name:
        return {"success": False, "error": f"TỪ CHỐI: '{path}' là thư mục hệ thống quan trọng, không thể xóa!"}

    try:
        if os.path.isfile(path):
            os.unlink(path)
            return {"success": True, "output": f"Đã xóa file: {path}"}
        elif os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=False)
            if not os.path.exists(path):
                return {"success": True, "output": f"Đã xóa thư mục: {path}"}
    except Exception:
        pass

    try:
        if os.path.isfile(path):
            _run(f'takeown /F "{path}" /D Y 2>nul', shell=True, timeout=30)
            _run(f'icacls "{path}" /grant Everyone:F /T /Q 2>nul', shell=True, timeout=30)
            _run(f'del /F /Q "{path}"', shell=True, timeout=30)
        elif os.path.isdir(path):
            _run(f'takeown /F "{path}" /R /D Y 2>nul', shell=True, timeout=60)
            _run(f'icacls "{path}" /grant Everyone:F /T /Q 2>nul', shell=True, timeout=60)
            _run(f'rmdir /S /Q "{path}"', shell=True, timeout=60)

        if not os.path.exists(path):
            return {"success": True, "output": f"Đã xóa (force): {path}"}
        else:
            return {"success": False, "error": "Không thể xóa. Thư mục đang được sử dụng."}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def get_defender_status() -> dict:
    """Lấy trạng thái Windows Defender."""
    ok, output = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "Get-MpComputerStatus | Select-Object -Property RealTimeProtectionEnabled,AntivirusEnabled,QuickScanEndTime,FullScanEndTime | ConvertTo-Json"],
        timeout=20,
    )

    if not ok:
        return {"enabled": False, "error": "Không thể truy cập Windows Defender."}

    import json
    try:
        status = json.loads(output)
        return {
            "enabled": status.get("AntivirusEnabled", False),
            "realtime": status.get("RealTimeProtectionEnabled", False),
            "quick_scan": status.get("QuickScanEndTime", ""),
            "full_scan": status.get("FullScanEndTime", ""),
        }
    except json.JSONDecodeError:
        return {"enabled": False, "error": "Không thể解析 dữ liệu Defender."}


# --------------------------------------------------------------------------- #
# Windows Repair - SFC, DISM, chkdsk
# --------------------------------------------------------------------------- #

def run_sfc() -> dict:
    """Chạy System File Checker (sfc /scannow)."""
    ok, out = _run("sfc /scannow", shell=True, timeout=600)
    return {"success": ok, "output": out}

def run_dism() -> dict:
    """Chạy DISM RestoreHealth."""
    ok, out = _run("DISM /Online /Cleanup-Image /RestoreHealth", shell=True, timeout=600)
    return {"success": ok, "output": out}

def run_dism_scanhealth() -> dict:
    """Chạy DISM ScanHealth (chỉ quét không sửa)."""
    ok, out = _run("DISM /Online /Cleanup-Image /ScanHealth", shell=True, timeout=300)
    return {"success": ok, "output": out}

def run_chkdsk(drive: str = "C:") -> dict:
    """Chạy chkdsk /f trên ổ đĩa."""
    ok, out = _run(f'chkdsk {drive} /f', shell=True, timeout=300)
    return {"success": ok, "output": out}


# --------------------------------------------------------------------------- #
# Firewall toggle
# --------------------------------------------------------------------------- #

def get_firewall_status() -> dict:
    """Kiểm tra tường lửa Windows Defender đang bật/tắt."""
    ok, out = _run("netsh advfirewall show allprofiles state", shell=True, timeout=15)
    enabled = "ON" in out.upper() if out else False
    return {"enabled": enabled, "output": out}

def set_firewall(on: bool) -> dict:
    """Bật/tắt tường lửa Windows Defender (tắt hoàn toàn, không thông báo)."""
    state = "on" if on else "off"
    ok, out = _run(f"netsh advfirewall set allprofiles state {state}", shell=True, timeout=15)
    return {"success": ok, "enabled": on, "output": out}


# --------------------------------------------------------------------------- #
# Driver Scanner
# --------------------------------------------------------------------------- #

def scan_drivers() -> list[dict]:
    """Quét danh sách driver bằng pnputil, trả về thông tin chi tiết."""
    drivers = []
    ok, out = _run("pnputil /enum-drivers", shell=True, timeout=30)
    if not out:
        return drivers

    current = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if ": " in line and not line.startswith(" ") and not line.startswith("Published"):
            key, val = line.split(": ", 1)
            current[key.strip()] = val.strip()
        elif line.startswith("Published Name"):
            if current:
                drivers.append(current)
            current = {"Published Name": line.split(":", 1)[1].strip()}
        elif ": " in line:
            parts = line.split(": ", 1)
            current[parts[0].strip()] = parts[1].strip()
    if current:
        drivers.append(current)

    # Parse driver date, flag old ones
    import datetime
    now = datetime.date.today()
    for d in drivers:
        ver_str = d.get("Driver Version", "")
        if ver_str:
            parts = ver_str.split(" ", 1)
            date_str = parts[0] if parts else ""
            try:
                d_date = datetime.datetime.strptime(date_str, "%m/%d/%Y").date()
                d["driver_date"] = d_date.isoformat()
                age = (now - d_date).days
                d["age_days"] = age
                d["needs_update"] = age > 365
            except (ValueError, IndexError):
                d["driver_date"] = ""
                d["age_days"] = 0
                d["needs_update"] = False
        else:
            d["driver_date"] = ""
            d["age_days"] = 0
            d["needs_update"] = False

    drivers.sort(key=lambda x: x.get("age_days", 0), reverse=True)
    return drivers
