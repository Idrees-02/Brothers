# PyInstaller spec for Brothers for Selling Carpet.
# Build (on Windows, from the project root):
#   pyinstaller packaging/brothers.spec
# Output goes to dist/Brothers/ (onedir build - faster startup, easier to debug
# than onefile, and Inno Setup just packages the whole folder).

import os

block_cipher = None
project_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(SPEC)), ".."))
icon_path = os.path.join(project_root, "app", "resources", "icons", "app.ico")

a = Analysis(
    [os.path.join(project_root, "app", "main.py")],
    pathex=[project_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, "app", "resources"), "app/resources"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Brothers",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=icon_path if os.path.exists(icon_path) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Brothers",
)
