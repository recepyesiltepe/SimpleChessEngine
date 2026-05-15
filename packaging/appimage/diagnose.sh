#!/usr/bin/env bash
# Help debug a built AppImage or AppDir (run from repo root).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APPDIR="${ROOT}/build/appimage/AppDir"
APPIMAGE="$(ls -1 "${ROOT}"/build/appimage/*.AppImage 2>/dev/null | head -1 || true)"
LOG="${HOME}/.cache/simple-chess-engine/launch.log"

echo "Log file: ${LOG}"
echo

if [[ -d "${APPDIR}" ]]; then
  echo "=== AppDir launcher ==="
  APPIMAGE_DEBUG=1 bash "${APPDIR}/AppRun" || true
  echo
fi

if [[ -n "${APPIMAGE}" && -f "${APPIMAGE}" ]]; then
  echo "=== AppImage (extract and run) ==="
  chmod a+x "${APPIMAGE}"
  APPIMAGE_EXTRACT_AND_RUN=1 APPIMAGE_DEBUG=1 "${APPIMAGE}" || true
  echo
fi

if [[ -f "${LOG}" ]]; then
  echo "=== Last 40 lines of launch.log ==="
  tail -40 "${LOG}"
else
  echo "No launch.log yet."
fi
