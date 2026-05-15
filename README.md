# Simple Chess Engine

A desktop chess game with a **GTK 4** interface and a built-in Python engine. Play against the AI, use clocks, browse move history, and work with FEN/PGN.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![GTK](https://img.shields.io/badge/GTK-4-green)

## Features

- **AI opponent** — Easy, Medium, Hard, and Expert (search depth 2–7)
- **Opening book** and improved evaluation (piece-square tables, king safety, passed pawns)
- **Time controls** — From 1+0 to 30+0, plus increment options
- **Board themes** — Classic, Forest, Marble, Unicode large
- **Drag-and-drop** moves, hints, undo, resign
- **FEN / PGN** — Load, copy, save, paste
- **Move replay** — Arrow keys, keyboard shortcuts
- **Material panel** and **evaluation bar**
- **Optional move sounds**
- **Responsive layout** — Landscape and portrait; scales on smaller screens

## Downloads

Pre-built binaries are on the [Releases](https://github.com/recepyesiltepe/SimpleChessEngine/releases) page.

| Platform | File | Notes |
|----------|------|--------|
| **Linux** | `*.AppImage` | `chmod +x SimpleChessEngine-*.AppImage` then run. Needs FUSE or extract with `--appimage-extract`. |
| **Windows** | `SimpleChessEngine-windows-ucrt64.zip` | Unzip and run `SimpleChessEngine.exe`. Keep the `_internal` folder next to the exe. |

Launch log (if something fails):

- Linux AppImage: `~/.cache/simple-chess-engine/launch.log`
- Windows: `%LOCALAPPDATA%\simple-chess-engine\launch.log`

## Run from source

### Linux

Install GTK 4 and PyGObject (distro packages are easiest), then:

```bash
git clone https://github.com/recepyesiltepe/SimpleChessEngine.git
cd SimpleChessEngine
python -m venv .venv
source .venv/bin/activate
pip install -e .
python main.py
```

**Arch Linux example:**

```bash
sudo pacman -S python python-gobject gtk4
pip install -e .
python main.py
```

### Windows

Use **MSYS2 UCRT64** with GTK4, PyGObject, and Python from `mingw-w64-ucrt-x86_64-*` packages, then `pip install -e .` and `python main.py`.  
For a standalone folder/exe, see [packaging/windows](packaging/windows/) and the GitHub Actions workflow **Windows EXE**.

## Build packages yourself

### Linux AppImage (x86_64)

```bash
./packaging/appimage/build.sh
# Output: build/appimage/*.AppImage
```

Requires: `bash`, `curl`, `tar`, and network access (downloads micromamba and appimagetool).

### Windows onedir bundle

On **windows-latest** CI, or locally in MSYS2 UCRT64:

```bash
bash packaging/windows/build-mingw.sh
# Output: dist/SimpleChessEngine/
```

## Controls

| Input | Action |
|-------|--------|
| Click / drag | Move pieces |
| **← / →** | Step through game history |
| **Enter** | Jump to a move number (replay mode) |
| **Esc** | Clear selection |

## Project layout

```
engine/          # Rules, AI (negamax + quiescence), FEN/PGN, opening book
gui.py           # GTK 4 UI
main.py          # Entry point
theme_data.py    # Board color themes
user_prefs.py    # Saved settings
packaging/       # AppImage and Windows PyInstaller scripts
sounds/          # Optional WAV feedback
```

