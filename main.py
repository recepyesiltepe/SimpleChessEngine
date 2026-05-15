from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _win_log_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "simple-chess-engine" / "launch.log"


def _win_log(msg: str) -> None:
    path = _win_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(msg.rstrip() + "\n")


def _win_show_error(message: str) -> None:
    _win_log(f"ERROR: {message}")
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(  # type: ignore[attr-defined]
            0,
            f"{message}\n\nDetails: {_win_log_path()}",
            "Simple Chess Engine",
            0x10,
        )
    except Exception:
        print(message, file=sys.stderr)
        print(f"Log: {_win_log_path()}", file=sys.stderr)


def _bootstrap_frozen_windows() -> None:
    if not getattr(sys, "frozen", False):
        return

    def _hook(exc_type, exc, tb) -> None:
        _win_log("".join(traceback.format_exception(exc_type, exc, tb)))
        _win_show_error(str(exc))

    sys.excepthook = _hook
    _win_log("=== Simple Chess Engine start ===")

    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        if not Gtk.init_check():
            raise RuntimeError("Gtk.init_check() failed")
        _win_log("GTK preflight OK")
    except Exception as exc:
        _win_show_error(f"GTK failed to load:\n{exc}")
        raise SystemExit(1) from exc


def main() -> int:
    _bootstrap_frozen_windows()
    from gui import run

    try:
        return run(ai_depth=3)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1
    except Exception as exc:
        if getattr(sys, "frozen", False):
            _win_show_error(str(exc))
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())
