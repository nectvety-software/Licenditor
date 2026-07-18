"""
repair_sdcard_windows.py
========================
Cong cu format va sua chua the nho/USB tren Windows.
Chay voi quyen Administrator de hoat dong tot nhat.

Su dung:
    python repair_sdcard_windows.py
    python repair_sdcard_windows.py --drive E
    python repair_sdcard_windows.py --drive E --fs exFAT --label MY_USB
    python repair_sdcard_windows.py --drive E --repair
    python repair_sdcard_windows.py --drive E --diagnose
"""

from __future__ import annotations

import os
import sys
import json
import re
import subprocess
import argparse
from typing import Optional


IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    try:
        import winreg
    except ImportError:
        winreg = None
else:
    winreg = None


# --------------------------------------------------------------------------- #
# Colors for terminal
# --------------------------------------------------------------------------- #

class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def colored(text: str, color: str) -> str:
    if IS_WINDOWS:
        os.system("")
    return f"{color}{text}{Colors.END}"


def print_header(text: str) -> None:
    print(f"\n{colored('=' * 60, Colors.CYAN)}")
    print(colored(f"  {text}", Colors.BOLD + Colors.CYAN))
    print(colored("=" * 60, Colors.CYAN))


def print_success(text: str) -> None:
    print(f"  {colored('[OK]', Colors.GREEN)} {text}")


def print_error(text: str) -> None:
    print(f"  {colored('[LOI]', Colors.RED)} {text}")


def print_warning(text: str) -> None:
    print(f"  {colored('[CANH BAO]', Colors.YELLOW)} {text}")


def print_info(text: str) -> None:
    print(f"  {colored('[*]', Colors.BLUE)} {text}")


# --------------------------------------------------------------------------- #
# System commands
# --------------------------------------------------------------------------- #

def run_cmd(cmd, shell: bool = False, timeout: int = 60) -> tuple[bool, str]:
    """Chay lenh he thong an toan."""
    creationflags = 0
    startupinfo = None
    if IS_WINDOWS:
        creationflags = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    try:
        out = subprocess.check_output(
            cmd, shell=shell, stderr=subprocess.STDOUT,
            timeout=timeout, creationflags=creationflags, startupinfo=startupinfo,
        )
        return True, out.decode("utf-8", errors="ignore")
    except Exception as exc:
        return False, str(exc)


def run_powershell(script: str, timeout: int = 30) -> tuple[bool, str]:
    return run_cmd(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        timeout=timeout,
    )


# --------------------------------------------------------------------------- #
# Drive detection
# --------------------------------------------------------------------------- #

def detect_removable_drives() -> list[dict]:
    """Phat hien cac o dia di dong (USB, the nho)."""
    if not IS_WINDOWS:
        return []

    drives = []
    ok, output = run_powershell(
        "Get-Volume | Where-Object { $_.DriveType -eq 'Removable' -or "
        "($_.DriveLetter -and $_.Size -gt 0) } | "
        "Select-Object DriveLetter,FileSystemLabel,FileSystem,Size,SizeRemaining,"
        "HealthStatus,DriveType | ConvertTo-Json -Depth 3"
    )

    if not ok or not output.strip():
        return []

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
                "drive_type": v.get("DriveType", ""),
                "path": f"{letter}:\\",
            })
    except json.JSONDecodeError:
        pass

    return drives


def format_size(size_bytes: int) -> str:
    """Dinh dang kich thuoc."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


# --------------------------------------------------------------------------- #
# Drive diagnosis
# --------------------------------------------------------------------------- #

def diagnose_drive(drive_letter: str) -> dict:
    """Chuan doan chi tiet tinh trang o dia."""
    result = {
        "drive": drive_letter,
        "is_raw": False,
        "is_readonly": False,
        "is_accessible": False,
        "filesystem": "",
        "health": "Unknown",
        "total_bytes": 0,
        "free_bytes": 0,
        "issues": [],
        "recommendations": [],
    }

    ok, output = run_powershell(
        f"Get-Volume -DriveLetter {drive_letter} | "
        "Select-Object FileSystem,FileSystemLabel,Size,SizeRemaining,HealthStatus,DriveType | "
        "ConvertTo-Json -Depth 3"
    )

    if ok and output.strip():
        try:
            vol = json.loads(output)
            fs = vol.get("FileSystem", "")
            result["filesystem"] = fs or "RAW"
            result["label"] = vol.get("FileSystemLabel", "")
            result["total_bytes"] = vol.get("Size", 0)
            result["free_bytes"] = vol.get("SizeRemaining", 0)
            result["health"] = vol.get("HealthStatus", "Unknown")
            result["drive_type"] = vol.get("DriveType", "")

            if not fs or fs.upper() == "RAW":
                result["is_raw"] = True
                result["issues"].append("O dia o trang thai RAW (khong co file system)")
                result["recommendations"].append("Can format o dia de su dung duoc")
            elif fs.upper() not in ("NTFS", "FAT32", "exFAT"):
                result["issues"].append(f"File system khong pho bien: {fs}")
                result["recommendations"].append("Nen format lai thanh NTFS hoac exFAT")
        except json.JSONDecodeError:
            pass

    ok2, ro_out = run_powershell(
        f"Get-Disk | Where-Object {{ $_.Number -eq (Get-Partition -DriveLetter {drive_letter}).DiskNumber }} | "
        "Select-Object IsReadOnly,IsOffline,OperationalStatus | ConvertTo-Json"
    )
    if ok2 and ro_out.strip():
        try:
            disk = json.loads(ro_out)
            if isinstance(disk, list):
                disk = disk[0] if disk else {}
            if disk.get("IsReadOnly"):
                result["is_readonly"] = True
                result["issues"].append("O dia o che do read-only (chi doc)")
                result["recommendations"].append("Can tat read-only truoc khi ghi du lieu")
            if disk.get("IsOffline"):
                result["issues"].append("O dia dang offline")
                result["recommendations"].append("Can set o dia online truoc khi su dung")
        except json.JSONDecodeError:
            pass

    ok3, acc_out = run_powershell(f"Test-Path '{drive_letter}:\\'")
    if ok3 and "True" in acc_out:
        result["is_accessible"] = True
    else:
        result["issues"].append("Khong the truy cap o dia")
        result["recommendations"].append("O dia co the bi hoac can format")

    if not result["issues"]:
        result["issues"].append("Khong phat hien van de")
        result["recommendations"].append("O dia hoat dong binh thuong")

    return result


# --------------------------------------------------------------------------- #
# Repair functions
# --------------------------------------------------------------------------- #

def fix_readonly(drive_letter: str) -> dict:
    """Tat che do read-only cua o dia."""
    ok, output = run_powershell(
        f"$disk = Get-Disk | Where-Object {{ $_.Number -eq (Get-Partition -DriveLetter {drive_letter}).DiskNumber }}; "
        f"if ($disk.IsReadOnly) {{ $disk | Set-Disk -IsReadOnly $false; 'Da tat read-only' }} "
        f"else {{ 'Read-only da tat hoac khong ap dung' }}"
    )
    return {"success": ok, "output": output.strip() if ok else output}


def set_disk_online(drive_letter: str) -> dict:
    """Set o dia online neu dang offline."""
    ok, output = run_powershell(
        f"$disk = Get-Disk | Where-Object {{ $_.Number -eq (Get-Partition -DriveLetter {drive_letter}).DiskNumber }}; "
        f"if ($disk.IsOffline) {{ $disk | Set-Disk -IsOffline $false; 'Da set online' }} "
        f"else {{ 'O dia da online hoac khong tim thay' }}"
    )
    return {"success": ok, "output": output.strip() if ok else output}


def repair_filesystem(drive_letter: str) -> dict:
    """Sua chua file system bang chkdsk."""
    diag = diagnose_drive(drive_letter)
    issues = []

    if diag.get("is_raw"):
        return {
            "success": False,
            "output": "O dia RAW - khong the chay chkdsk. Can format lai.",
            "issues": ["O dia o trang thai RAW"],
        }

    if diag.get("is_readonly"):
        fix_result = fix_readonly(drive_letter)
        issues.append(f"Da tat read-only: {fix_result.get('output', '')}")

    ok, output = run_cmd(f"chkdsk {drive_letter}: /R /F", shell=True, timeout=180)

    if not ok and "read-only" in output.lower():
        issues.append("O dia dang read-only, thu tat...")
        fix_readonly(drive_letter)
        ok2, output2 = run_cmd(f"chkdsk {drive_letter}: /R /F", shell=True, timeout=180)
        return {"success": ok2, "output": output2, "issues": issues}

    return {"success": ok, "output": output, "issues": issues}


def format_drive(drive_letter: str, filesystem: str = "exFAT",
                 label: str = "USB_DRIVE", quick: bool = True) -> dict:
    """Format o dia voi xu ly loi chi tiet."""
    issues = []

    diag = diagnose_drive(drive_letter)
    if diag.get("is_readonly"):
        fix_result = fix_readonly(drive_letter)
        issues.append(f"Da tat read-only: {fix_result.get('output', '')}")

    flag = "/Q" if quick else ""
    ok, output = run_cmd(
        f"format {drive_letter}: /FS:{filesystem} /V:{label} {flag} /Y",
        shell=True, timeout=300,
    )

    if not ok:
        if "can't format" in output.lower() or "cannot format" in output.lower():
            issues.append("Windows khong the format - thu dung diskpart")
            dp_ok, dp_out = run_cmd("echo clean | diskpart", shell=True, timeout=30)
            if dp_ok:
                ok2, output2 = run_cmd(
                    f"format {drive_letter}: /FS:{filesystem} /V:{label} {flag} /Y",
                    shell=True, timeout=300,
                )
                return {
                    "success": ok2,
                    "output": output2,
                    "issues": issues + ["Da dung diskpart clean roi format lai"],
                }

    return {"success": ok, "output": output, "issues": issues}


# --------------------------------------------------------------------------- #
# Interactive menu
# --------------------------------------------------------------------------- #

def show_drive_list(drives: list[dict]) -> None:
    """Hien thi danh sach o dia."""
    print_header("DANH SACH O DIA DI DONG")

    if not drives:
        print_warning("Khong tim thay o dia di dong (USB/the nho)")
        print_info("Hay gan the nho/USB vao may va thu lai")
        return

    for i, d in enumerate(drives, 1):
        total = d.get("total_bytes", 0)
        free = d.get("free_bytes", 0)
        used = total - free
        fs = d.get("filesystem", "RAW")
        label = d.get("label", "N/A")
        health = d.get("health", "Unknown")

        print(f"\n  {colored(f'[{i}]', Colors.BOLD)} O dia: {colored(d['letter'] + ':', Colors.BOLD + Colors.CYAN)}")
        print(f"      Nhan: {label or 'Khong co nhan'}")
        print(f"      File system: {fs}")
        print(f"      Dung luong: {format_size(used)} / {format_size(total)} (con trong: {format_size(free)})")
        print(f"      Trang thai: {health}")


def select_drive(drives: list[dict]) -> Optional[dict]:
    """Cho phep nguoi dung chon o dia."""
    if not drives:
        return None

    while True:
        try:
            choice = input(f"\n  {colored('Chon o dia (so thu tu):', Colors.BOLD)} ").strip()
            if not choice:
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(drives):
                return drives[idx]
            print_error("Lua chon khong hop le!")
        except (ValueError, EOFError):
            return None


def show_menu() -> str:
    """Hien thi menu chinh."""
    print(f"\n{colored('  CHON THAO TAC:', Colors.BOLD)}")
    print(f"  {colored('[1]', Colors.CYAN)} Chuan doan chi tiet")
    print(f"  {colored('[2]', Colors.CYAN)} Sua chua file system (chkdsk)")
    print(f"  {colored('[3]', Colors.CYAN)} Tat read-only")
    print(f"  {colored('[4]', Colors.CYAN)} Format exFAT (nhanh)")
    print(f"  {colored('[5]', Colors.CYAN)} Format FAT32 (nhanh)")
    print(f"  {colored('[6]', Colors.CYAN)} Format NTFS (nhanh)")
    print(f"  {colored('[7]', Colors.CYAN)} Format exFAT (day du)")
    print(f"  {colored('[8]', Colors.CYAN)} Format FAT32 (day du)")
    print(f"  {colored('[9]', Colors.CYAN)} Format NTFS (day du)")
    print(f"  {colored('[0]', Colors.RED)} Quay lai / Thoat")
    print()

    try:
        return input(f"  {colored('Nhap lua chon:', Colors.BOLD)} ").strip()
    except EOFError:
        return "0"


def run_diagnose(drive: dict) -> None:
    """Chay chuan doan chi tiet."""
    letter = drive["letter"]
    print_header(f"CHUAN DOAN O DIA {letter}:")

    print_info("Dang quet...")
    result = diagnose_drive(letter)

    print(f"\n  {colored('KET QUA:', Colors.BOLD)}")
    print(f"    File system: {result.get('filesystem', 'N/A')}")
    print(f"    Nhan: {result.get('label', 'N/A')}")
    print(f"    Dung luong: {format_size(result.get('total_bytes', 0))}")
    print(f"    Trang thai: {result.get('health', 'Unknown')}")
    print(f"    Truy cap: {'Co' if result.get('is_accessible') else 'Khong'}")
    print(f"    Read-only: {'Co' if result.get('is_readonly') else 'Khong'}")
    print(f"    RAW: {'Co' if result.get('is_raw') else 'Khong'}")

    issues = result.get("issues", [])
    recs = result.get("recommendations", [])

    if issues:
        print(f"\n  {colored('VAN DE PHAT HIEN:', Colors.YELLOW)}")
        for issue in issues:
            print(f"    {colored('-', Colors.YELLOW)} {issue}")

    if recs:
        print(f"\n  {colored('GOI Y:', Colors.GREEN)}")
        for rec in recs:
            print(f"    {colored('>', Colors.GREEN)} {rec}")


def run_repair(drive: dict) -> None:
    """Chay sua chua file system."""
    letter = drive["letter"]
    print_header(f"SUA CHUA FILE SYSTEM {letter}:")

    confirm = input(f"  {colored('Ban co chac muon sua chua? (y/N):', Colors.YELLOW)} ").strip().lower()
    if confirm != "y":
        print_info("Da huy")
        return

    print_info("Dang sua chua (co the mat thoi gian)...")
    result = repair_filesystem(letter)

    issues = result.get("issues", [])
    for issue in issues:
        print_info(issue)

    if result.get("success"):
        print_success("Sua chua hoan tat!")
    else:
        print_error("Sua chua that bai")
        output = result.get("output", "")
        if output:
            print(f"\n  {colored('Chi tiet loi:', Colors.RED)}")
            for line in output[:500].split("\n"):
                print(f"    {line}")


def run_format(drive: dict, filesystem: str, quick: bool = True) -> None:
    """Chay format o dia."""
    letter = drive["letter"]
    print_header(f"FORMAT O DIA {letter}: ({filesystem})")

    if not quick:
        print_warning("Format day du se mat nhieu thoi gian hon!")
    print_warning("TAT CA DU LIEU SE BI XOA HOAN TOAN!")

    confirm = input(f"  {colored('Ban CO CHAC MUON format? (nhap YES de xac nhan):', Colors.RED)} ").strip()
    if confirm != "YES":
        print_info("Da huy")
        return

    label = input(f"  {colored('Nhan o dia (mac dinh: USB_DRIVE):', Colors.BOLD)} ").strip() or "USB_DRIVE"

    print_info(f"Dang format {filesystem}...")
    result = format_drive(letter, filesystem, label, quick)

    issues = result.get("issues", [])
    for issue in issues:
        print_info(issue)

    if result.get("success"):
        print_success("Format hoan tat!")
        print_info(f"O dia {letter}: da duoc format thanh {filesystem}")
        print_info(f"Nhan: {label}")
    else:
        print_error("Format that bai")
        output = result.get("output", "")
        if output:
            print(f"\n  {colored('Chi tiet loi:', Colors.RED)}")
            for line in output[:500].split("\n"):
                print(f"    {line}")


def run_fix_readonly(drive: dict) -> None:
    """Tat read-only."""
    letter = drive["letter"]
    print_header(f"TAT READ-ONLY {letter}:")

    print_info("Dang tat read-only...")
    result = fix_readonly(letter)
    print_success(result.get("output", "Hoan tat"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cong cu format va sua chua the nho/USB tren Windows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Vi du:
  python repair_sdcard_windows.py                    # Chay giao dien tuong tac
  python repair_sdcard_windows.py --drive E          # Chuan doan o dia E
  python repair_sdcard_windows.py --drive E --format exFAT
  python repair_sdcard_windows.py --drive E --repair
  python repair_sdcard_windows.py --drive E --diagnose
        """,
    )
    parser.add_argument("--drive", "-d", type=str, help="Ky hieu o dia (vd: E)")
    parser.add_argument("--diagnose", action="store_true", help="Chuan doan chi tiet")
    parser.add_argument("--repair", action="store_true", help="Sua chua file system")
    parser.add_argument("--fix-readonly", action="store_true", help="Tat read-only")
    parser.add_argument("--format", "-f", type=str, choices=["FAT32", "exFAT", "NTFS"],
                        help="Format o dia")
    parser.add_argument("--label", "-l", type=str, default="USB_DRIVE", help="Nhan o dia")
    parser.add_argument("--quick", action="store_true", default=True, help="Format nhanh")
    parser.add_argument("--full", action="store_true", help="Format day du")

    args = parser.parse_args()

    if not IS_WINDOWS:
        print_error("Cong cu nay chi hoat dong tren Windows!")
        return 1

    print_header("REPAIR SDCARD - CONG CU SUA CHUA THE NHO")
    print_info("Kiem tra o dia di dong...")

    drives = detect_removable_drives()

    if args.drive:
        target = args.drive.upper().rstrip(":")
        drive = next((d for d in drives if d["letter"] == target), None)
        if not drive:
            print_error(f"Khong tim thay o dia {target}:")
            show_drive_list(drives)
            return 1
    else:
        if not drives:
            print_error("Khong tim thay o dia di dong!")
            print_info("Hay gan the nho/USB vao may va thu lai")
            return 1
        show_drive_list(drives)
        drive = select_drive(drives)
        if not drive:
            return 0

    letter = drive["letter"]
    print_info(f"Da chon o dia {letter}: ({drive.get('label', 'N/A')})")

    if args.diagnose:
        run_diagnose(drive)
        return 0

    if args.fix_readonly:
        run_fix_readonly(drive)
        return 0

    if args.repair:
        run_repair(drive)
        return 0

    if args.format:
        quick = not args.full
        run_format(drive, args.format, quick)
        return 0

    while True:
        choice = show_menu()

        if choice == "0":
            print_info("Tam biet!")
            break
        elif choice == "1":
            run_diagnose(drive)
        elif choice == "2":
            run_repair(drive)
        elif choice == "3":
            run_fix_readonly(drive)
        elif choice == "4":
            run_format(drive, "exFAT", quick=True)
        elif choice == "5":
            run_format(drive, "FAT32", quick=True)
        elif choice == "6":
            run_format(drive, "NTFS", quick=True)
        elif choice == "7":
            run_format(drive, "exFAT", quick=False)
        elif choice == "8":
            run_format(drive, "FAT32", quick=False)
        elif choice == "9":
            run_format(drive, "NTFS", quick=False)
        else:
            print_error("Lua chon khong hop le!")

        drives = detect_removable_drives()
        drive = next((d for d in drives if d["letter"] == letter), None)
        if not drive:
            print_error(f"O dia {letter}: da bi rut khoi may!")
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
