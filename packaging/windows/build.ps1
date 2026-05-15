# Build a Windows onedir bundle with PyInstaller (run from MSYS2 UCRT64/MINGW64 where GTK Python works).
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

python -m pip install -U pip
python -m pip install -r requirements.txt pyinstaller pyinstaller-hooks-contrib

$schemaDir = python -c "import sys; from pathlib import Path; print(Path(sys.prefix) / 'share' / 'glib-2.0' / 'schemas')"
if ((Get-Command glib-compile-schemas -ErrorAction SilentlyContinue) -and (Test-Path $schemaDir)) {
  glib-compile-schemas $schemaDir
}

python -m PyInstaller --clean --noconfirm (Join-Path $PSScriptRoot "simple-chess-engine.spec")
bash (Join-Path $PSScriptRoot "copy-msys2-runtime.sh")

Write-Host "Done. Run: dist\SimpleChessEngine\SimpleChessEngine.exe"
