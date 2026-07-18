import sys
import os
import shutil
import subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON = os.path.join(BASE, "libs", "app-icon", "icon.ico")
OUT = os.path.join(BASE, "dist")
SPEC = os.path.join(BASE, "scripts", "licenditor.spec")

os.makedirs(OUT, exist_ok=True)

fonts = os.path.join(BASE, "app", "resources")
spec = os.path.join(BASE, "scripts", "licenditor.spec")

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--noconsole",
    "--name", "Licenditor",
    "--icon", ICON,
    "--distpath", OUT,
    "--workpath", os.path.join(BASE, "build"),
    "--specpath", os.path.join(BASE, "scripts"),
    "--add-data", f"{ICON};app-icon",
    "--add-data", f"{fonts};app/resources",
    "--hidden-import", "PySide6.QtNetwork",
    os.path.join(BASE, "main.py"),
]

print(" ".join(cmd))
result = subprocess.run(cmd, cwd=BASE)
if result.returncode != 0:
    print("Build failed!")
    sys.exit(1)

print(f"Done: {os.path.join(OUT, 'Licenditor.exe')}")
