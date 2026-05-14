"""PyInstaller runtime hook: help GTK/GI find bundled DLLs and typelibs (Windows onedir)."""
from __future__ import annotations

import os
import sys


if getattr(sys, "frozen", False):
    exe_dir = os.path.dirname(sys.executable)
    internal = os.path.join(exe_dir, "_internal")
    bases = [internal, exe_dir] if os.path.isdir(internal) else [exe_dir]

    path_dirs: list[str] = []
    for b in bases:
        for sub in ("", "bin"):
            p = os.path.join(b, sub) if sub else b
            if os.path.isdir(p):
                path_dirs.append(p)
    os.environ["PATH"] = os.pathsep.join(path_dirs + [os.environ.get("PATH", "")])

    gi_parts: list[str] = []
    for b in bases:
        for rel in ("lib/girepository-1.0", "Library/lib/girepository-1.0"):
            p = os.path.join(b, *rel.split("/"))
            if os.path.isdir(p):
                gi_parts.append(p)
    if gi_parts:
        prev = os.environ.get("GI_TYPELIB_PATH", "")
        os.environ["GI_TYPELIB_PATH"] = os.pathsep.join(gi_parts + ([prev] if prev else []))

    data_parts: list[str] = []
    for b in bases:
        p = os.path.join(b, "share")
        if os.path.isdir(p):
            data_parts.append(p)
    if data_parts:
        prev = os.environ.get("XDG_DATA_DIRS", "")
        os.environ["XDG_DATA_DIRS"] = os.pathsep.join(data_parts + ([prev] if prev else []))
