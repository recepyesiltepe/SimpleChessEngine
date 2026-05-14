# Build a Windows onedir bundle with PyInstaller (run from MSYS2 UCRT64/MINGW64 where GTK Python works).
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

python -m pip install -U pip
python -m pip install -r requirements.txt pyinstaller pyinstaller-hooks-contrib
python -m PyInstaller --clean --noconfirm (Join-Path $PSScriptRoot "simple-chess-engine.spec")

Write-Host "Done. Run: dist\SimpleChessEngine\SimpleChessEngine.exe"
