#!/usr/bin/env bash
# Build Windows onedir with PyInstaller (MSYS2 MinGW/UCRT shell with GTK Python on PATH).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

python -m pip install -U pip
python -m pip install -r requirements.txt pyinstaller pyinstaller-hooks-contrib

if command -v glib-compile-schemas >/dev/null 2>&1; then
  SCHEMA_DIR="$(python -c "import sys; from pathlib import Path; print(Path(sys.prefix)/'share/glib-2.0/schemas')")"
  if [[ -d "$SCHEMA_DIR" ]]; then
    glib-compile-schemas "$SCHEMA_DIR"
  fi
fi

python -m PyInstaller --clean --noconfirm packaging/windows/simple-chess-engine.spec
bash packaging/windows/copy-msys2-runtime.sh

echo "Done. Run: dist/SimpleChessEngine/SimpleChessEngine.exe"
