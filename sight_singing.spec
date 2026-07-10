# -*- mode: python ; coding: utf-8 -*-
"""Stage 11: PyInstaller spec for the standalone offline .exe.

Build with:  pyinstaller sight_singing.spec
Output:      dist/SightSingingStudio.exe (single file, zero-config)

Only read-only, ship-with-the-app assets are bundled (templates, static,
the exercise catalog, the pre-trained solfège classifier). Uploads are
written next to the .exe at runtime (see app/config.py) and never shipped.
"""
a = Analysis(
    ["run_app.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("app/templates", "app/templates"),
        ("app/static", "app/static"),
        ("app/data/songs", "app/data/songs"),
        ("app/models", "app/models"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # This dev machine's shared Python env has torch (CUDA build) and other
    # unrelated ML frameworks installed for other projects. scikit-learn's
    # optional array-API hooks pull them in as multi-GB dead weight if not
    # excluded -- this app never imports any of them.
    excludes=[
        "torch", "torchaudio", "torchvision",
        "tensorflow", "matplotlib", "IPython", "jupyter", "notebook", "pytest",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SightSingingStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
