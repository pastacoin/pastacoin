# -*- mode: python ; coding: utf-8 -*-
# One-file Windows build of the desktop app:  pyinstaller PastaMachine.spec  ->  dist/PastaMachine.exe

a = Analysis(
    ['pasta/frontends/desktop/__main__.py'],
    pathex=['.'],                      # find the pasta package from the source tree, however it is installed
    binaries=[],
    datas=[],
    hiddenimports=['pasta.frontends.desktop.app'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'tkinter', 'pytest'],
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
    name='PastaMachine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
