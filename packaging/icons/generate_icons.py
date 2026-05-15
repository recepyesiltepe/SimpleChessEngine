#!/usr/bin/env python3
"""Generate Linux PNG icons from chess.ico (repo root) for AppImage/desktop."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SOURCE = ROOT / "chess.ico"
LINUX_SIZES = (16, 32, 48, 64, 128, 256)
APP_NAME = "simple-chess-engine"


def _load_rgba() -> Image.Image:
    img = Image.open(SOURCE)
    if getattr(img, "n_frames", 1) > 1:
        best_i = 0
        best_area = 0
        for i in range(img.n_frames):
            img.seek(i)
            area = img.size[0] * img.size[1]
            if area > best_area:
                best_area = area
                best_i = i
        img.seek(best_i)
    img = img.convert("RGBA")
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a > 0 and r > 235 and g > 235 and b > 235:
                pixels[x, y] = (r, g, b, 0)
    return img


def _fit_square(img: Image.Image, size: int) -> Image.Image:
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    w, h = img.size
    side = max(w, h)
    pad = max(4, int(side * 0.06))
    canvas = Image.new("RGBA", (side + 2 * pad, side + 2 * pad), (0, 0, 0, 0))
    canvas.paste(img, ((canvas.width - w) // 2, (canvas.height - h) // 2), img)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Missing icon: {SOURCE}")

    base = _load_rgba()

    master_path = HERE / f"{APP_NAME}.png"
    _fit_square(base, 256).save(master_path, format="PNG")
    print(f"wrote {master_path}")

    for size in LINUX_SIZES:
        out = HERE / "hicolor" / f"{size}x{size}" / "apps" / f"{APP_NAME}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        _fit_square(base, size).save(out, format="PNG")
        print(f"wrote {out}")

    print(f"Windows icon: use {SOURCE} (PyInstaller spec references chess.ico)")


if __name__ == "__main__":
    main()
