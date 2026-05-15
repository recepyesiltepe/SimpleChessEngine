"""PyInstaller runtime hook: bundle-only DLL paths for GTK/GI (Windows onedir)."""
from __future__ import annotations

import os
import sys


if getattr(sys, "frozen", False):
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    internal = os.path.join(exe_dir, "_internal")
    bases = [internal, exe_dir] if os.path.isdir(internal) else [exe_dir]

    path_dirs: list[str] = []
    for b in bases:
        for sub in ("", "bin"):
            p = os.path.join(b, sub) if sub else b
            if os.path.isdir(p):
                path_dirs.append(os.path.abspath(p))
                if hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(p)

    if path_dirs:
        os.environ["PATH"] = os.pathsep.join(path_dirs)

    gi_parts: list[str] = []
    for b in bases:
        for rel in ("lib/girepository-1.0", "Library/lib/girepository-1.0"):
            p = os.path.join(b, *rel.split("/"))
            if os.path.isdir(p):
                gi_parts.append(p)
    if gi_parts:
        os.environ["GI_TYPELIB_PATH"] = os.pathsep.join(gi_parts)

    data_parts: list[str] = []
    for b in bases:
        p = os.path.join(b, "share")
        if os.path.isdir(p):
            data_parts.append(p)
    if data_parts:
        os.environ["XDG_DATA_DIRS"] = os.pathsep.join(data_parts)

    for b in bases:
        pixbuf_lib = os.path.join(b, "lib", "gdk-pixbuf-2.0")
        if not os.path.isdir(pixbuf_lib):
            continue
        for name in sorted(os.listdir(pixbuf_lib)):
            vdir = os.path.join(pixbuf_lib, name)
            if not os.path.isdir(vdir):
                continue
            loaders = os.path.join(vdir, "loaders")
            cache = os.path.join(vdir, "loaders.cache")
            if os.path.isdir(loaders):
                os.environ["GDK_PIXBUF_MODULEDIR"] = loaders
            if os.path.isfile(cache):
                os.environ["GDK_PIXBUF_MODULE_FILE"] = cache
            break

    schemas = os.path.join(internal if os.path.isdir(internal) else exe_dir, "share", "glib-2.0", "schemas")
    if os.path.isdir(schemas):
        os.environ["GSETTINGS_SCHEMA_DIR"] = schemas

    for cert in (
        os.path.join(internal, "ssl", "cacert.pem"),
        os.path.join(exe_dir, "ssl", "cacert.pem"),
    ):
        if os.path.isfile(cert):
            os.environ["SSL_CERT_FILE"] = cert
            break

    os.environ["PYTHONNOUSERSITE"] = "1"
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ.pop("PYTHONHOME", None)
