# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for bundling Flask app
Run: pyinstaller flask_server.spec
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all Flask templates and static files
# Note: instance folder will be created at runtime in the app directory
datas = [
    ('templates', 'templates'),
    ('static', 'static'),
]

# Collect all Python modules
hiddenimports = [
    'flask',
    'flask_sqlalchemy',
    'flask_cors',
    'sqlalchemy',
    'werkzeug',
    'apscheduler',
    'models',
    'backup_manager',
    'backup_database',
    'backup_scheduler',
    'restore_database',
]

# Add any additional hidden imports
try:
    hiddenimports += collect_submodules('flask')
    hiddenimports += collect_submodules('sqlalchemy')
except:
    pass

a = Analysis(
    ['flask_server.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='flask_server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX compression for better compatibility
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Hide console window in production
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

