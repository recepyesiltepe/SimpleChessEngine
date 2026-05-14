# Running and checking on Windows

This project is **Python** (no separate compile step). Use a **64-bit Python** that matches your GTK stack.

## 1. Install GTK 4 + PyGObject (required)

PyGObject needs native GTK. The usual approach is **MSYS2** (MINGW64 or UCRT64):

1. Install [MSYS2](https://www.msys2.org/).
2. In the correct environment (e.g. **UCRT64**), install packages such as:
   - `mingw-w64-ucrt-x86_64-gtk4`
   - `mingw-w64-ucrt-x86_64-python-gobject`
   - `mingw-w64-ucrt-x86_64-python-cairo`
   - `mingw-w64-ucrt-x86_64-python` (if you use the MSYS Python)
3. Run the app from that same environment so `PATH` includes GTK DLLs.

Other community setups (gvsbuild, etc.) work as long as **the same interpreter** can `import gi` and `import cairo`.

## 2. Python dependencies

From the repository root (using the Python that has GTK):

```bat
python -m pip install -U pip
python -m pip install -r requirements.txt
```

Optional editable install (uses `pyproject.toml`):

```bat
python -m pip install -e .
```

## 3. Verify bytecode (optional)

```bat
python -m compileall -q .
```

## 4. Run

```bat
python main.py
```

## Settings file

On Windows, preferences are stored under `%APPDATA%\\simple-chess-engine\\settings.json` (see `user_prefs.py`).

## Sounds

WAV files in `sounds/` are played with **`winsound`** when available; otherwise the code falls back to Gdk beeps (same as Linux without a player).
