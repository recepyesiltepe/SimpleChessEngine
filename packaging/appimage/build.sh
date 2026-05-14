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
  gtk4 pygobject pycairo cairo \
  ca-certificates

echo "Installing application (no PyPI wheels for gi/cairo; use conda stack)…"
"${APPDIR}/usr/bin/pip" install --no-cache-dir --no-deps "${ROOT}"

echo "Bundling AppRun, desktop, icon…"
install -m755 "${ROOT}/packaging/appimage/AppRun" "${APPDIR}/AppRun"
install -m644 "${ROOT}/packaging/appimage/simple-chess-engine.desktop" \
  "${APPDIR}/usr/share/applications/simple-chess-engine.desktop"
install -m644 "${ROOT}/packaging/appimage/simple-chess-engine.desktop" \
  "${APPDIR}/simple-chess-engine.desktop"

# Minimal valid PNG (1×1) for AppImage metadata; replace with a real icon if you prefer.
ICON64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
echo "${ICON64}" | base64 -d > "${APPDIR}/simple-chess-engine.png"
cp -f "${APPDIR}/simple-chess-engine.png" "${APPDIR}/.DirIcon"

echo "Building AppImage (version ${VERSION})…"
cd "${OUTDIR}"
ARCH=x86_64 VERSION="${VERSION}" "${APPIMAGETOOL}" "${APPDIR}"

echo "Done."
ls -la "${OUTDIR}"/*.AppImage 2>/dev/null || ls -la .
