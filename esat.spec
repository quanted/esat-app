# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/resources/icons/*.svg', 'resources/icons'),
        ('src/resources/icons/*.png', 'resources/icons'),
        ('src/resources/icons/*.ico', 'resources/icons'),
        ('src/resources/icons/*.gif', 'resources/icons'),
        ('src/resources/styles/*.qss', 'resources/styles'),
        ('src/resources/content/*.json', 'resources/content'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'setuptools',
        'wheel',
        'pip',
        'packaging',
        'pefile',
        'mdurl',
        'markdown-it-py',
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='esat',
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['src\\resources\\icons\\favicon.ico'],
    splash='src\\resources\\icons\\esat-logo.png',
    onefile=True,
)

