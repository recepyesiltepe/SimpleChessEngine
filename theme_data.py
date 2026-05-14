from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoardTheme:
    name: str
    light_sq: tuple[float, float, float]
    dark_sq: tuple[float, float, float]
    selected: tuple[float, float, float]
    move_hint: tuple[float, float, float]
    last_light: tuple[float, float, float]
    last_dark: tuple[float, float, float]
    hint_light: tuple[float, float, float]
    hint_dark: tuple[float, float, float]
    piece_font: str
    piece_rgb: tuple[float, float, float]


THEMES: dict[str, BoardTheme] = {
    "Classic": BoardTheme(
        name="Classic",
        light_sq=(0.941, 0.851, 0.710),
        dark_sq=(0.713, 0.533, 0.388),
        selected=(0.910, 0.890, 0.431),
        move_hint=(0.545, 0.765, 0.286),
        last_light=(0.969, 0.925, 0.454),
        last_dark=(0.855, 0.765, 0.294),
        hint_light=(0.620, 0.784, 1.0),
        hint_dark=(0.357, 0.525, 0.761),
        piece_font="Serif 40",
        piece_rgb=(0.067, 0.067, 0.067),
    ),
    "Forest": BoardTheme(
        name="Forest",
        light_sq=(0.78, 0.88, 0.78),
        dark_sq=(0.35, 0.52, 0.38),
        selected=(0.85, 0.92, 0.55),
        move_hint=(0.45, 0.75, 0.45),
        last_light=(0.88, 0.95, 0.72),
        last_dark=(0.55, 0.72, 0.48),
        hint_light=(0.55, 0.82, 0.95),
        hint_dark=(0.30, 0.48, 0.62),
        piece_font="Serif 40",
        piece_rgb=(0.05, 0.12, 0.06),
    ),
    "Marble": BoardTheme(
        name="Marble",
        light_sq=(0.92, 0.92, 0.94),
        dark_sq=(0.55, 0.58, 0.62),
        selected=(0.95, 0.88, 0.55),
        move_hint=(0.65, 0.78, 0.92),
        last_light=(0.98, 0.96, 0.82),
        last_dark=(0.72, 0.74, 0.78),
        hint_light=(0.72, 0.86, 1.0),
        hint_dark=(0.42, 0.55, 0.72),
        piece_font="Serif 40",
        piece_rgb=(0.08, 0.08, 0.10),
    ),
    "Unicode large": BoardTheme(
        name="Unicode large",
        light_sq=(0.941, 0.851, 0.710),
        dark_sq=(0.713, 0.533, 0.388),
        selected=(0.910, 0.890, 0.431),
        move_hint=(0.545, 0.765, 0.286),
        last_light=(0.969, 0.925, 0.454),
        last_dark=(0.855, 0.765, 0.294),
        hint_light=(0.620, 0.784, 1.0),
        hint_dark=(0.357, 0.525, 0.761),
        piece_font="Serif 44",
        piece_rgb=(0.067, 0.067, 0.067),
    ),
}

DEFAULT_THEME = "Classic"
