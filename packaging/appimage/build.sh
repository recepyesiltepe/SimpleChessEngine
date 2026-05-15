#!/usr/bin/env bash
# Build SimpleChessEngine-x86_64.AppImage on Linux (x86_64) using micromamba + conda-forge.
# Requires: bash, curl, tar, bzip2, glibc, FUSE (or extract-only) for running appimagetool.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTDIR="${ROOT}/build/appimage"
APPDIR="${OUTDIR}/AppDir"
CACHE="${OUTDIR}/cache"
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "${ROOT}/pyproject.toml" | head -1)"
VERSION="${VERSION:-0.1.0}"

MICROMAMBA="${CACHE}/micromamba"
APPIMAGETOOL="${CACHE}/appimagetool"

mkdir -p "${CACHE}" "${OUTDIR}"

if [[ ! -x "${MICROMAMBA}" ]]; then
  echo "Downloading micromamba…"
  mkdir -p "${CACHE}/micromamba-extract"
  curl -fsSL "https://micro.mamba.pm/api/micromamba/linux-64/latest" \
    | tar -xj -C "${CACHE}/micromamba-extract" bin/micromamba
  install -m755 "${CACHE}/micromamba-extract/bin/micromamba" "${MICROMAMBA}"
fi

if [[ ! -x "${APPIMAGETOOL}" ]]; then
  echo "Downloading appimagetool…"
  curl -fsSL -o "${APPIMAGETOOL}" \
    "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
  chmod a+x "${APPIMAGETOOL}"
fi

echo "Cleaning AppDir…"
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr"

echo "Creating relocatable prefix (conda-forge)…"
"${MICROMAMBA}" create -y -p "${APPDIR}/usr" -c conda-forge \
  "python=3.11" pip setuptools wheel \
  gtk4 pygobject pycairo cairo gdk-pixbuf \
  glib glib-tools adwaita-icon-theme \
  ca-certificates

echo "Installing application (no PyPI wheels for gi/cairo; use conda stack)…"
"${APPDIR}/usr/bin/pip" install --no-cache-dir --no-deps "${ROOT}"

echo "Compiling GLib schemas and gdk-pixbuf loader cache…"
export PATH="${APPDIR}/usr/bin:${PATH}"
SCHEMA_DIR="${APPDIR}/usr/share/glib-2.0/schemas"
if [[ -d "${SCHEMA_DIR}" ]] && command -v glib-compile-schemas >/dev/null; then
  glib-compile-schemas "${SCHEMA_DIR}"
fi
# Regenerate loaders.cache with paths relative to this prefix (relocatable AppImage).
PIXBUF_ROOT="${APPDIR}/usr/lib/gdk-pixbuf-2.0"
if command -v gdk-pixbuf-query-loaders >/dev/null; then
  for loaders_dir in "${PIXBUF_ROOT}"/*/loaders; do
    if [[ -d "${loaders_dir}" ]]; then
      cache_file="$(dirname "${loaders_dir}")/loaders.cache"
      gdk-pixbuf-query-loaders "${loaders_dir}" >"${cache_file}"
      echo "Wrote ${cache_file}"
    fi
  done
fi
"${APPDIR}/usr/bin/python" -c "
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
assert Gtk.init_check()
print('GTK OK:', Gtk.get_major_version())
"

echo "Bundling AppRun, desktop, icon…"
install -m755 "${ROOT}/packaging/appimage/AppRun" "${APPDIR}/AppRun"
install -m644 "${ROOT}/packaging/appimage/simple-chess-engine.desktop" \
  "${APPDIR}/usr/share/applications/simple-chess-engine.desktop"
install -m644 "${ROOT}/packaging/appimage/simple-chess-engine.desktop" \
  "${APPDIR}/simple-chess-engine.desktop"

ICON_PNG="${ROOT}/packaging/icons/simple-chess-engine.png"
if [[ ! -f "${ICON_PNG}" ]] && [[ -f "${ROOT}/chess.ico" ]]; then
  echo "Generating Linux icons from chess.ico…"
  "${ROOT}/packaging/icons/generate_icons.py"
fi
if [[ ! -f "${ICON_PNG}" ]]; then
  echo "error: missing ${ICON_PNG} (run packaging/icons/generate_icons.py)" >&2
  exit 1
fi
install -m644 "${ICON_PNG}" "${APPDIR}/simple-chess-engine.png"
cp -f "${ICON_PNG}" "${APPDIR}/.DirIcon"
mkdir -p "${APPDIR}/usr/share/icons"
cp -a "${ROOT}/packaging/icons/hicolor" "${APPDIR}/usr/share/icons/"

echo "Building AppImage (version ${VERSION})…"
cd "${OUTDIR}"
ARCH=x86_64 VERSION="${VERSION}" "${APPIMAGETOOL}" "${APPDIR}"

APPIMAGE_PATH="$(ls -1 "${OUTDIR}"/*.AppImage 2>/dev/null | head -1 || true)"
if [[ -n "${APPIMAGE_PATH}" ]]; then
  chmod a+x "${APPIMAGE_PATH}"
  echo "Built: ${APPIMAGE_PATH}"
fi

echo "Done."
ls -la "${OUTDIR}"/*.AppImage 2>/dev/null || ls -la .
