$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaseDir = Split-Path -Parent $ScriptDir
$ISCC = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"

Write-Output "=== Step 1: Build .exe with PyInstaller ==="
python "$ScriptDir\build_exe.py"
if (-not $?) { exit 1 }

Write-Output "`n=== Step 2: Build installer with Inno Setup ==="
if (-not (Test-Path $ISCC)) {
    Write-Error "Inno Setup not found: $ISCC"
    exit 1
}
& $ISCC "$ScriptDir\installer.iss"
if (-not $?) { exit 1 }

$Setup = Get-ChildItem "$BaseDir\dist\Licenditor_Setup*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($Setup) {
    Write-Output "`n=== Done: $($Setup.FullName) ==="
} else {
    Write-Error "Installer not found in dist/"
}
