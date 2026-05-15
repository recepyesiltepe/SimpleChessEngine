#!/usr/bin/env bash
# Copy MSYS2 UCRT64/MINGW GTK runtime DLLs into the PyInstaller onedir (_internal).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUNDLE="${ROOT}/dist/SimpleChessEngine"
INTERNAL="${BUNDLE}/_internal"

if [[ ! -d "$INTERNAL" ]]; then
  echo "error: expected PyInstaller output at $INTERNAL" >&2
  exit 1
fi

PREFIX="$(python -c "import sys; print(sys.prefix)")"

copy_dll_dir() {
  local dir="$1"
  [[ -d "$dir" ]] || return 0
  local n=0
  shopt -s nullglob
  for dll in "$dir"/*.dll; do
    cp -f "$dll" "$INTERNAL/"
    n=$((n + 1))
  done
  echo "  copied $n DLLs from $dir"
}

echo "MSYS2 prefix: $PREFIX"
copy_dll_dir "${PREFIX}/bin"
copy_dll_dir "${PREFIX}/lib"

# Copy DLLs listed by pacman for GTK stack packages (handles versioned names like libgtk-4-1-0.dll).
if command -v pacman >/dev/null 2>&1; then
  pkgs=(
    mingw-w64-ucrt-x86_64-gtk4
    mingw-w64-ucrt-x86_64-glib2
    mingw-w64-ucrt-x86_64-gdk-pixbuf2
    mingw-w64-ucrt-x86_64-pango
    mingw-w64-ucrt-x86_64-cairo
    mingw-w64-ucrt-x86_64-harfbuzz
    mingw-w64-ucrt-x86_64-fribidi
  )
  n=0
  while read -r _path; do
    [[ -f "$_path" ]] || continue
    cp -f "$_path" "$INTERNAL/"
    n=$((n + 1))
  done < <(pacman -Ql "${pkgs[@]}" 2>/dev/null | awk '{print $2}' | grep -E '\.dll$' || true)
  echo "  copied $n DLLs from pacman package file lists"
fi

GI_REPO="${PREFIX}/lib/girepository-1.0"
if [[ -d "$GI_REPO" ]]; then
  mkdir -p "$INTERNAL/lib/girepository-1.0"
  cp -f "$GI_REPO"/* "$INTERNAL/lib/girepository-1.0/" 2>/dev/null || true
fi

PIX="${PREFIX}/lib/gdk-pixbuf-2.0"
if [[ -d "$PIX" ]]; then
  mkdir -p "$INTERNAL/lib"
  cp -a "$PIX" "$INTERNAL/lib/"
fi

for rel in share/glib-2.0/schemas share/gtk-4.0; do
  src="${PREFIX}/${rel}"
  if [[ -d "$src" ]]; then
    mkdir -p "$INTERNAL/$(dirname "$rel")"
    cp -a "$src" "$INTERNAL/$(dirname "$rel")/"
  fi
done

# MSYS2 GTK4 often ships libgtk-4-1.dll only (Gdk merged into Gtk; no libgdk-4-*.dll).
gtk_dll="$(find "$INTERNAL" -maxdepth 1 -iname 'libgtk-4*.dll' -print -quit 2>/dev/null || true)"
if [[ -z "$gtk_dll" ]]; then
  echo "error: libgtk-4*.dll missing in $INTERNAL after copy" >&2
  ls -la "${PREFIX}/bin"/libgtk-4*.dll "$INTERNAL"/libgtk-4*.dll 2>&1 || true
  exit 1
fi
gdk_dll="$(find "$INTERNAL" -maxdepth 1 -iname 'libgdk-4*.dll' -print -quit 2>/dev/null || true)"
if [[ -n "$gdk_dll" ]]; then
  echo "GTK runtime OK: $(basename "$gtk_dll"), $(basename "$gdk_dll")"
else
  echo "GTK runtime OK: $(basename "$gtk_dll") (no separate libgdk-4 DLL on this MSYS2 build)"
fi
