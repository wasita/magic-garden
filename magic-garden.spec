# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec file for Magic Garden Auto-Buyer
#
# To build the executable:
#   1. Install PyInstaller: pip install pyinstaller
#   2. Run: pyinstaller magic-garden.spec
#   3. Find executable in dist/ folder
#
# Notes:
#   - This builds a LIGHTWEIGHT version using only Pytesseract (not EasyOCR)
#   - Tesseract OCR must be installed separately on the target machine
#   - For EasyOCR support, users should run from source with: pip install easyocr
#

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Lightweight build - exclude heavy ML dependencies
# EasyOCR/PyTorch are optional and can be installed separately if needed
hidden_imports = [
    'PIL', 'PIL.Image', 'numpy', 'pytesseract',
    'cv2', 'pynput', 'pynput.keyboard', 'pynput.mouse',
]

# Exclude heavy packages to keep build small
excludes = [
    'torch', 'torchvision', 'torchaudio',
    'easyocr',
    'tensorflow', 'keras',
    'matplotlib', 'scipy', 'pandas',
    'IPython', 'jupyter',
    'playwright',  # DOM mode requires separate install
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config.json', '.'),
        ('templates', 'templates'),
        ('src', 'src'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
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
    name='MagicGardenBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Set to False for windowed mode (no console)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one: icon='icon.ico'
)

# For macOS .app bundle (optional)
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='MagicGardenBot.app',
        icon=None,  # Add icon path here: icon='icon.icns'
        bundle_identifier='com.magicgarden.bot',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'NSAccessibilityUsageDescription': 'Magic Garden Bot needs accessibility access to control mouse and keyboard.',
        },
    )
