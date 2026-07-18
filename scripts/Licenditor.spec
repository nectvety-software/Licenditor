# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\Program\\licenditor\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('D:\\Program\\licenditor\\libs\\app-icon\\icon.ico', 'app-icon'), ('D:\\Program\\licenditor\\app\\resources', 'app/resources')],
    hiddenimports=['PySide6.QtNetwork'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Licenditor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:\\Program\\licenditor\\libs\\app-icon\\icon.ico'],
)
