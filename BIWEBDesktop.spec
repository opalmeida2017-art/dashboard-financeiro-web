# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: pyinstaller BIWEBDesktop.spec
# O robô Chrome roda headless no .exe (biweb_launcher define ROBO_HEADLESS=true).

import sys
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / 'biweb_launcher.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'templates'), 'templates'),
        (str(ROOT / 'static'), 'static'),
        (str(ROOT / 'sql'), 'sql'),
        (str(ROOT / 'alembic'), 'alembic'),
        (str(ROOT / 'alembic.ini'), '.'),
    ],
    hiddenimports=[
        'engineio.async_drivers.threading',
        'flask_login',
        'psycopg2',
        'pandas',
        'selenium',
        'weasyprint',
        'rembg',
        'PIL',
        'dotenv',
    ],
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
    name='BIWEB',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
