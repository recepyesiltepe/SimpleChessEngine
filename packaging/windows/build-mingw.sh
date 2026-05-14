#!/usr/bin/env bash
# Build Windows onedir with PyInstaller (MSYS2 MinGW/UCRT shell with GTK Python on PATH).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

python -m pip install -U pip
python -m pip install -r requirements.txt pyinstaller pyinstaller-hooks-contrib
python -m PyInstaller --clean --noconfirm packaging/windows/simple-chess-engine.spec

echo "Done. Run: dist/SimpleChessEngine/SimpleChessEngine.exe"
