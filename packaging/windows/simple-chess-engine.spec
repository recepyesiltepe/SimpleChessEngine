# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Windows (build with MSYS2 MinGW Python + GTK4 + PyGObject on PATH).
from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

# Directory that contains this .spec file (PyInstaller 5+).
try:
    _spec_dir = Path(SPECPATH).resolve()  # type: ignore[name-defined]
except NameError:  # pragma: no cover
    _spec_dir = Path(__file__).resolve().parent

ROOT = _spec_dir.parents[1]

block_cipher = None

datas: list = []
binaries: list = []
hiddenimports: list = []

for pkg in ("gi", "cairo"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

try:
    hiddenimports += collect_submodules("engine")
except Exception:
    hiddenimports += [
        "engine",
        "engine.ai",
        "engine.evaluation",
        "engine.fen",
        "engine.opening_book",
        "engine.pgn",
        "engine.state",
        "engine.zobrist",
    ]

hiddenimports += [
    "gi.repository.Gtk",
    "gi.repository.Gdk",
    "gi.repository.Gio",
    "gi.repository.GLib",
    "gi.repository.Pango",
    "gi.repository.PangoCairo",
    "cairo",
    "gui",
    "theme_data",
    "user_prefs",
    "main",
]

sounds_dir = ROOT / "sounds"
if sounds_dir.is_dir():
    datas += [(str(sounds_dir), "sounds")]

_app_icon = _spec_dir / "app.ico"
_exe_icon = str(_app_icon) if _app_icon.is_file() else None

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(_spec_dir / "pyi_rth_gtk.py")],
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
    [],
    exclude_binaries=True,
    name="SimpleChessEngine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_exe_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SimpleChessEngine",
)
