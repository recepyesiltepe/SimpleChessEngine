# Windows executable (PyInstaller)

This produces a **onedir** bundle: `dist/SimpleChessEngine/SimpleChessEngine.exe` plus a `_internal` folder with DLLs and data. You must **build on Windows** with the same **MSYS2 MinGW/UCRT Python + GTK4 + PyGObject** stack used to run the app (see [WINDOWS.md](../WINDOWS.md)).

## Prerequisites

1. MSYS2 with **UCRT64** (or **MINGW64**) environment.
2. Packages (example for UCRT64; prefix may differ):
   - `mingw-w64-ucrt-x86_64-gtk4`
   - `mingw-w64-ucrt-x86_64-python-gobject`
   - `mingw-w64-ucrt-x86_64-python-cairo`
   - `mingw-w64-ucrt-x86_64-python`
3. Open the **UCRT64** shell (not plain MSYS), `cd` to the repo root, and confirm:

   ```bash
   python -c "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk; import cairo; print('ok')"
   ```

## Build

**PowerShell** (from repo root or any directory):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build.ps1
```

**Bash** (UCRT64 / MINGW64):

```bash
bash packaging/windows/build-mingw.sh
```

**Manual:**

```bash
python -m pip install -U pip
python -m pip install -r requirements.txt pyinstaller pyinstaller-hooks-contrib
python -m PyInstaller --clean --noconfirm packaging/windows/simple-chess-engine.spec
```

Optional: `pip install -e ".[windows-exe]"` installs PyInstaller from `pyproject.toml` optional dependencies.

## Output and distribution

- **Launcher:** `dist/SimpleChessEngine/SimpleChessEngine.exe`
- **Payload:** `dist/SimpleChessEngine/_internal/` (keep the whole `SimpleChessEngine` folder when copying or zipping).

Zip the **`SimpleChessEngine`** directory for distribution. Do not ship only the `.exe` without `_internal`.

## Icon

Place `packaging/windows/app.ico` before building to set the executable icon. If the file is missing, PyInstaller builds without a custom icon.

## Runtime hook

`packaging/windows/pyi_rth_gtk.py` prepends the bundle and `_internal` to `PATH`, and sets `GI_TYPELIB_PATH` / `XDG_DATA_DIRS` when those folders exist, so GObject introspection can find typelibs and GTK data after freezing.

## Antivirus

PyInstaller bootloaders are sometimes flagged as false positives. If that happens, users may need an exception, or you can try code-signing the `.exe`.

## Cross-compile from Linux

PyInstaller cannot reliably bundle **Windows GTK** from Linux in this setup. Build on Windows (or a Windows VM/CI runner) with MSYS2 as above.

## Linux, Wine, and Proton

On **Linux**, use the native app (`python main.py` or an AppImage), not the Windows `.exe`.

**Wine / Proton** (Steam’s Proton, Bottles, etc.) is aimed at games and common Win32 APIs. **GTK 4 + GObject Introspection** is a full GUI stack (typelibs, many DLLs, GLib schemas, GDK backends). Even if the bundle includes typelibs, the stack often **does not run correctly** under Wine, and **Proton in particular is a poor fit** for GTK apps.

If you see `Namespace Gdk not available` on real **Windows** after a rebuild, the bundle was missing typelibs; rebuild with the current spec (it copies `lib/girepository-1.0` and GTK share data from the MSYS2 prefix used at build time). If the error appears **only under Wine/Proton**, treat that as unsupported and use the Linux build instead.

## GitHub Actions

This repository includes [`.github/workflows/windows-exe.yml`](../.github/workflows/windows-exe.yml). It runs on **`windows-latest`**, installs **MSYS2 UCRT64** packages (same stack as [WINDOWS.md](../WINDOWS.md)), runs `packaging/windows/build-mingw.sh`, and uploads **`SimpleChessEngine-windows-ucrt64`** containing the full `dist/SimpleChessEngine/` folder (exe + `_internal`).

**How to use it**

1. Push the workflow file to your default branch (or merge a PR that adds it).
2. In GitHub: **Actions** → **Windows EXE** → **Run workflow** (manual runs use **workflow_dispatch**). It also runs on push to `main` or `master` when relevant paths change.
3. When the job finishes, open the run → **Artifacts** → download the zip. Unzip it and run `SimpleChessEngine.exe` inside the folder (keep `_internal` next to it).

To build on every pull request as well, add a `pull_request:` trigger to that workflow file.
