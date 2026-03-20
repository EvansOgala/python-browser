# -*- mode: python ; coding: utf-8 -*-

import os

datas = [("org.evans.PythonBrowser.svg", ".")]
icon_file = "app_icon.ico" if os.path.exists("app_icon.ico") else None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "storage",
        "pyside_ui",
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "win_webview2_ui",
        "webview",
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
        "pythonnet",
        "clr",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "gi",
        "gi.repository",
        "gi.overrides",
        "ui",
        "gtk_style",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PythonBrowser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PythonBrowser",
)
