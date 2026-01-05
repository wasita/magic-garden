# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec file for Magic Garden Auto-Buyer
#
# To build the executable:
#   1. Install PyInstaller: pip install pyinstaller
#   2. Ensure Tesseract is installed at C:\Program Files\Tesseract-OCR (Windows)
#   3. Run: pyinstaller magic-garden.spec
#   4. Find executable in dist/ folder
#

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect EasyOCR data files (models, etc.)
easyocr_datas = collect_data_files('easyocr')

# Collect all submodules for packages that need them
hidden_imports = (
    collect_submodules('easyocr') +
    collect_submodules('torch') +
    collect_submodules('cv2') +
    ['PIL', 'PIL.Image', 'numpy', 'pytesseract']
)

# pydirectinput is Windows-only
if sys.platform == 'win32':
    hidden_imports.append('pydirectinput')

# Platform-specific binaries
binaries = []
datas = [
    ('config.json', '.'),
    ('templates', 'templates'),
    ('src', 'src'),
] + easyocr_datas

# Bundle Tesseract on Windows
if sys.platform == 'win32':
    tesseract_path = r'C:\Program Files\Tesseract-OCR'
    if os.path.exists(tesseract_path):
        # Add Tesseract executable and DLLs
        for f in os.listdir(tesseract_path):
            full_path = os.path.join(tesseract_path, f)
            if os.path.isfile(full_path):
                binaries.append((full_path, 'tesseract'))
        # Add tessdata (language models)
        tessdata_path = os.path.join(tesseract_path, 'tessdata')
        if os.path.exists(tessdata_path):
            datas.append((tessdata_path, 'tesseract/tessdata'))
    else:
        print(f"WARNING: Tesseract not found at {tesseract_path}")
        print("The built executable will require Tesseract to be installed separately.")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch.cuda',
        'torch.distributed',
        'torch.testing',
        'torch.utils.tensorboard',
        'torch.utils.bottleneck',
        'torch.utils.mobile_optimizer',
        'torch.onnx',
        'torch.optim.lr_scheduler',
        'torch.backends.cudnn',
        'torch.backends.cuda',
        'tensorboard',
        'lightning',
        'pytorch_lightning',
    ],
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
