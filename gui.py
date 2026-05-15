from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from collections import Counter
from pathlib import Path

try:
    import cairo
except ImportError as exc:
    raise ImportError(
        "The GTK UI needs pycairo for Gtk.DrawingArea. Install with: pip install pycairo "
        "(on Linux you may use the distro package, e.g. python-cairo; on Windows use the "
        "same Python that has GTK4/PyGObject, often from MSYS2 UCRT64/MINGW64 packages)."
    ) from exc
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("PangoCairo", "1.0")
try:
    gi.require_foreign("cairo")
except ImportError:
    pass
from gi.repository import Gdk, Gio, GLib, Gtk, Pango, PangoCairo

from engine import (
    GameState,
    Move,
    SearchInfo,
    build_pgn,
    extract_coordinate_moves,
    get_game_status,
    get_legal_moves,
    has_insufficient_material,
    is_in_check,
    parse_fen,
    pick_move_with_analysis,
    replay_coordinate_moves,
    state_to_fen,
    evaluate_position,
)
from engine.ai import PIECE_VALUES
from theme_data import DEFAULT_THEME, THEMES, BoardTheme
from user_prefs import load_prefs, save_prefs


PIECE_TO_UNICODE = {
    "K": "♔",
    "Q": "♕",
    "R": "♖",
    "B": "♗",
    "N": "♘",
    "P": "♙",
    "k": "♚",
    "q": "♛",
    "r": "♜",
    "b": "♝",
    "n": "♞",
    "p": "♟",
}

DIFFICULTY_TO_DEPTH = {
    "Easy": 2,
    "Medium": 3,
    "Hard": 5,
    "Expert": 7,
}

CLOCK_OPTIONS: list[tuple[str, float | None, float | None]] = [
    ("No clock", None, None),
    ("1+0", 60.0, 0.0),
    ("2+1", 120.0, 1.0),
    ("3+0", 180.0, 0.0),
    ("3+2", 180.0, 2.0),
    ("5+0", 300.0, 0.0),
    ("5+3", 300.0, 3.0),
    ("10+0", 600.0, 0.0),
    ("15+10", 900.0, 10.0),
    ("30+0", 1800.0, 0.0),
]

_INITIAL_WHITE_PIECES = Counter(P=8, R=2, N=2, B=2, Q=1, K=1)
_INITIAL_BLACK_PIECES = Counter(p=8, r=2, n=2, b=2, q=1, k=1)

_CAPTURE_DISPLAY_ORDER = (
    ("Q", "q"),
    ("R", "r"),
    ("B", "b"),
    ("N", "n"),
    ("P", "p"),
)

# Layout: board scales between these square sizes; window fits the primary monitor.
_MIN_SQUARE_SIZE = 36
_MAX_SQUARE_SIZE = 96
_DEFAULT_SQUARE_SIZE = 80
_IDEAL_WINDOW_WIDTH = 1100
_IDEAL_WINDOW_HEIGHT = 760
_MIN_WINDOW_WIDTH = 640
_MIN_WINDOW_HEIGHT = 480
_PORTRAIT_MAX_WIDTH = 980
_PORTRAIT_MAX_HEIGHT = 720


def _set_clipboard_text(widget: Gtk.Widget, text: str) -> None:
    provider = Gdk.ContentProvider.new_for_bytes(
        "text/plain;charset=utf-8",
        GLib.Bytes.new(text.encode("utf-8")),
    )
    widget.get_clipboard().set_content(provider)


class ChessWindow(Gtk.ApplicationWindow):
    def __init__(self, application: Gtk.Application, ai_depth: int = 3) -> None:
        super().__init__(application=application, title="Python Chess Engine — GTK / Wayland-ready")
        self.ai_depth = max(1, min(int(ai_depth), 32))
        self.square_size = _DEFAULT_SQUARE_SIZE
        self.margin_left = 28
        self.margin_bottom = 28
        self._layout_portrait = False
        self.human_is_white = True

        self.state = GameState.initial()
        self.state_history: list[GameState] = [self.state]
        self.move_history: list[Move] = []
        self.selected_square: tuple[int, int] | None = None
        self.legal_moves: list[Move] = get_legal_moves(self.state)
        self.hint_move: Move | None = None
        self._ai_busy = False
        self._game_generation = 0
        self._end_announced = False
        self._human_resigned = False
        self.eval_bar_width = 28
        self._board_render_scale = 1.0
        self._board_render_ox = 0.0
        self._board_render_oy = 0.0

        self._white_clock_sec = 0.0
        self._black_clock_sec = 0.0
        self._clock_increment_sec = 0.0
        self._clocks_enabled = False
        self._timeout_black_wins: bool | None = None
        self._clock_tick_source_id: int | None = None
        self._last_clock_mono = time.monotonic()

        self._replay_view_idx = 0
        self._drag_pick: tuple[int, int] | None = None
        self._drag_start_xy: tuple[float, float] | None = None
        self._theme: BoardTheme = THEMES[DEFAULT_THEME]
        self._prefs: dict = load_prefs()
        self._last_search_info: SearchInfo | None = None
        self._last_search_root_white: bool = True

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(outer)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        controls.set_margin_top(8)
        controls.set_margin_start(8)
        controls.set_margin_end(8)
        controls.append(Gtk.Label(label="Difficulty:"))
        difficulty_names = list(DIFFICULTY_TO_DEPTH.keys())
        self.difficulty_dropdown = Gtk.DropDown.new_from_strings(difficulty_names)
        default_difficulty = "Hard"
        for name, depth in DIFFICULTY_TO_DEPTH.items():
            if depth == ai_depth:
                default_difficulty = name
                break
        self.difficulty_dropdown.set_selected(difficulty_names.index(default_difficulty))
        self.difficulty_dropdown.connect("notify::selected", self._on_difficulty_notify)
        controls.append(self.difficulty_dropdown)

        controls.append(Gtk.Label(label="Play as:"))
        self.side_dropdown = Gtk.DropDown.new_from_strings(["White", "Black"])
        self.side_dropdown.set_selected(0)
        self.side_dropdown.connect("notify::selected", self._on_side_notify)
        controls.append(self.side_dropdown)

        self.hint_button = Gtk.Button(label="Hint")
        self.hint_button.connect("clicked", lambda _b: self._show_hint())
        controls.append(self.hint_button)

        self.undo_button = Gtk.Button(label="Undo")
        self.undo_button.connect("clicked", lambda _b: self._undo_last_turn())
        controls.append(self.undo_button)

        self.restart_button = Gtk.Button(label="Restart")
        self.restart_button.connect("clicked", lambda _b: self._restart_game())
        controls.append(self.restart_button)

        outer.append(controls)

        tools = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        tools.set_margin_start(8)
        tools.set_margin_end(8)
        self.copy_fen_button = Gtk.Button(label="Copy FEN")
        self.copy_fen_button.connect("clicked", lambda _b: self._copy_fen_to_clipboard())
        tools.append(self.copy_fen_button)
        self.copy_pgn_button = Gtk.Button(label="Copy PGN")
        self.copy_pgn_button.connect("clicked", lambda _b: self._copy_pgn_to_clipboard())
        tools.append(self.copy_pgn_button)
        self.save_pgn_button = Gtk.Button(label="Save PGN…")
        self.save_pgn_button.connect("clicked", lambda _b: self._save_pgn_to_file())
        tools.append(self.save_pgn_button)
        self.resign_button = Gtk.Button(label="Resign")
        self.resign_button.connect("clicked", lambda _b: self._resign_game())
        tools.append(self.resign_button)
        self.load_fen_button = Gtk.Button(label="Load FEN…")
        self.load_fen_button.connect("clicked", lambda _b: self._open_load_fen_dialog())
        tools.append(self.load_fen_button)
        self.load_pgn_button = Gtk.Button(label="Paste PGN…")
        self.load_pgn_button.connect("clicked", lambda _b: self._open_paste_pgn_dialog())
        tools.append(self.load_pgn_button)
        outer.append(tools)

        prefs_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        prefs_row.set_margin_start(8)
        prefs_row.set_margin_end(8)
        prefs_row.append(Gtk.Label(label="Board theme:"))
        theme_names = list(THEMES.keys())
        self.theme_dropdown = Gtk.DropDown.new_from_strings(theme_names)
        self.theme_dropdown.set_selected(theme_names.index(DEFAULT_THEME))
        self.theme_dropdown.connect("notify::selected", self._on_theme_notify)
        prefs_row.append(self.theme_dropdown)
        prefs_row.append(Gtk.Label(label="Sounds:"))
        self.sounds_switch = Gtk.Switch()
        self.sounds_switch.set_active(False)
        self.sounds_switch.connect("notify::active", self._on_sounds_active_notify)
        prefs_row.append(self.sounds_switch)
        prefs_row.append(Gtk.Label(label="←/→ replay · Enter jump · Esc clear"))
        outer.append(prefs_row)

        clock_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        clock_row.set_margin_start(8)
        clock_row.set_margin_end(8)
        clock_row.set_margin_top(2)
        clock_row.set_margin_bottom(4)
        clock_row.append(Gtk.Label(label="Time control:"))
        clock_strings = [opt[0] for opt in CLOCK_OPTIONS]
        self.clock_dropdown = Gtk.DropDown.new_from_strings(clock_strings)
        self.clock_dropdown.set_selected(5)
        self.clock_dropdown.connect("notify::selected", self._on_clock_preset_notify)
        clock_row.append(self.clock_dropdown)
        clock_row.append(Gtk.Label(label="White:"))
        self.white_clock_label = Gtk.Label(label="—")
        self.white_clock_label.add_css_class("monospace")
        clock_row.append(self.white_clock_label)
        clock_row.append(Gtk.Label(label="Black:"))
        self.black_clock_label = Gtk.Label(label="—")
        self.black_clock_label.add_css_class("monospace")
        clock_row.append(self.black_clock_label)
        clock_row.append(Gtk.Label(label="+inc/move"))
        outer.append(clock_row)

        self._content_stack = Gtk.Stack()
        self._content_stack.set_vexpand(True)
        self._content_stack.set_hexpand(True)

        self._landscape_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self._landscape_box.set_vexpand(True)
        self._portrait_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._portrait_box.set_vexpand(True)

        self._board_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self._board_row.set_vexpand(True)
        self._board_row.set_hexpand(True)

        captured_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        captured_box.set_hexpand(False)
        self._captured_box = captured_box
        captured_box.append(Gtk.Label(label="Material", halign=Gtk.Align.START))
        self.captured_balance_label = Gtk.Label(label="")
        self.captured_balance_label.set_halign(Gtk.Align.START)
        captured_box.append(self.captured_balance_label)
        captured_box.append(Gtk.Label(label="Off board (White)", halign=Gtk.Align.START))
        self.captured_white_label = Gtk.Label(label="", wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        self.captured_white_label.set_halign(Gtk.Align.START)
        captured_box.append(self.captured_white_label)
        captured_box.append(Gtk.Label(label="Off board (Black)", halign=Gtk.Align.START))
        self.captured_black_label = Gtk.Label(label="", wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        self.captured_black_label.set_halign(Gtk.Align.START)
        captured_box.append(self.captured_black_label)
        self._board_row.append(captured_box)

        self.eval_drawing = Gtk.DrawingArea()
        self.eval_drawing.set_hexpand(False)
        self.eval_drawing.set_vexpand(True)
        self.eval_drawing.set_valign(Gtk.Align.FILL)
        self.eval_drawing.set_draw_func(self._draw_eval_bar, None)
        self._board_row.append(self.eval_drawing)

        self.board_drawing = Gtk.DrawingArea()
        self.board_drawing.set_hexpand(True)
        self.board_drawing.set_vexpand(True)
        self.board_drawing.set_valign(Gtk.Align.FILL)
        self.board_drawing.set_halign(Gtk.Align.FILL)
        self.board_drawing.set_draw_func(self._draw_board_canvas, None)
        click_gesture = Gtk.GestureClick()
        click_gesture.connect("pressed", self._on_board_pressed)
        self.board_drawing.add_controller(click_gesture)
        drag_gesture = Gtk.GestureDrag()
        drag_gesture.set_button(Gdk.BUTTON_PRIMARY)
        drag_gesture.connect("drag-begin", self._on_board_drag_begin)
        drag_gesture.connect("drag-end", self._on_board_drag_end)
        self.board_drawing.add_controller(drag_gesture)
        self._board_row.append(self.board_drawing)

        self._landscape_spacer = Gtk.Box()
        self._landscape_spacer.set_hexpand(True)

        history_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        history_box.set_hexpand(False)
        self._history_box = history_box
        history_box.append(Gtk.Label(label="Move History", halign=Gtk.Align.START))
        self._history_scroll = Gtk.ScrolledWindow()
        self._history_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._history_scroll.set_vexpand(True)
        self.history_view = Gtk.TextView()
        self.history_view.set_editable(False)
        self.history_view.set_cursor_visible(False)
        self.history_view.set_monospace(True)
        self.history_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._history_scroll.set_child(self.history_view)
        history_box.append(self._history_scroll)

        self._landscape_box.append(self._board_row)
        self._landscape_box.append(self._landscape_spacer)
        self._landscape_box.append(self._history_box)

        self._content_stack.add_named(self._landscape_box, "landscape")
        self._content_stack.add_named(self._portrait_box, "portrait")
        self._content_stack.set_visible_child_name("landscape")

        content_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_wrap.set_margin_start(8)
        content_wrap.set_margin_end(8)
        content_wrap.set_margin_bottom(8)
        content_wrap.set_vexpand(True)
        content_wrap.append(self._content_stack)
        outer.append(content_wrap)

        self._sync_board_dimensions()

        self.status_label = Gtk.Label(label="")
        self.status_label.set_margin_top(8)
        self.status_label.set_margin_bottom(4)
        outer.append(self.status_label)

        self.multipv_label = Gtk.Label(label="")
        self.multipv_label.set_wrap(True)
        self.multipv_label.set_xalign(0.0)
        self.multipv_label.add_css_class("dim-label")
        self.multipv_label.set_margin_start(12)
        self.multipv_label.set_margin_end(12)
        self.multipv_label.set_margin_bottom(8)
        outer.append(self.multipv_label)

        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctrl)

        self.connect("close-request", self._on_close_request)
        self.board_drawing.connect("notify::allocation", self._on_board_allocation_changed)
        self.connect("notify::default-width", self._on_window_metrics_changed)
        self.connect("notify::default-height", self._on_window_metrics_changed)
        self.connect("realize", self._on_window_realize)

        self._apply_initial_window_geometry()
        self._apply_saved_preferences()
        self._sync_replay_index_to_end()
        self._restart_clock_timer()
        self._refresh_ui()
        if self.state.white_to_move != self.human_is_white:
            self._after_ms(100, self._play_ai_turn)

    def _sync_board_dimensions(self) -> None:
        self.board_size = self.square_size * 8
        self.canvas_width = self.margin_left + self.board_size
        self.canvas_height = self.board_size + self.margin_bottom
        if not hasattr(self, "board_drawing"):
            return
        self.board_drawing.set_content_width(self.canvas_width)
        self.board_drawing.set_content_height(self.canvas_height)
        self.eval_drawing.set_content_width(self.eval_bar_width)
        self.eval_drawing.set_content_height(self.board_size)

    def _available_monitor_size(self) -> tuple[int, int]:
        display = Gdk.Display.get_default()
        if display is None:
            return 1920, 1080
        monitor = display.get_primary_monitor()
        if monitor is None:
            monitors = display.get_monitors()
            if monitors is not None and monitors.get_n_items() > 0:
                monitor = monitors.get_item(0)
        if monitor is None:
            return 1920, 1080
        geom = monitor.get_geometry()
        scale = monitor.get_scale_factor()
        return max(geom.width, 1) * scale, max(geom.height, 1) * scale

    def _apply_initial_window_geometry(self) -> None:
        sw, sh = self._available_monitor_size()
        usable_w = int(sw * 0.92)
        usable_h = int(sh * 0.88)
        w = min(_IDEAL_WINDOW_WIDTH, usable_w)
        h = min(_IDEAL_WINDOW_HEIGHT, usable_h)
        w = max(w, min(_MIN_WINDOW_WIDTH, usable_w))
        h = max(h, min(_MIN_WINDOW_HEIGHT, usable_h))
        self.set_default_size(w, h)

    def _dialog_min_width(self) -> int:
        w = self.get_width()
        if w > 1:
            return max(280, min(560, int(w * 0.88)))
        return 480

    def _on_window_realize(self, _window: Gtk.Window) -> None:
        self._update_responsive_layout()

    def _on_window_metrics_changed(self, _window: Gtk.Window, _pspec: object) -> None:
        self._update_responsive_layout()

    def _on_board_allocation_changed(self, widget: Gtk.Widget, _pspec: object) -> None:
        alloc = widget.get_allocation()
        if alloc.width < 8 or alloc.height < 8:
            return
        sq_w = int((alloc.width - self.margin_left) / 8)
        sq_h = int((alloc.height - self.margin_bottom) / 8)
        sq = min(sq_w, sq_h, _MAX_SQUARE_SIZE)
        sq = max(sq, _MIN_SQUARE_SIZE)
        if sq != self.square_size:
            self.square_size = sq
            self._sync_board_dimensions()
            self.board_drawing.queue_draw()
            self.eval_drawing.queue_draw()

    def _update_responsive_layout(self) -> None:
        w = self.get_width()
        h = self.get_height()
        if w < 2 or h < 2:
            return

        want_portrait = w < _PORTRAIT_MAX_WIDTH or h < _PORTRAIT_MAX_HEIGHT
        if want_portrait != self._layout_portrait:
            self._layout_portrait = want_portrait
            if want_portrait:
                if self._board_row.get_parent() is self._landscape_box:
                    self._landscape_box.remove(self._board_row)
                if self._history_box.get_parent() is self._landscape_box:
                    self._landscape_box.remove(self._history_box)
                if self._board_row.get_parent() is not self._portrait_box:
                    self._portrait_box.prepend(self._board_row)
                if self._history_box.get_parent() is not self._portrait_box:
                    self._portrait_box.append(self._history_box)
                self._history_box.set_vexpand(True)
                self._history_box.set_hexpand(True)
                self._content_stack.set_visible_child_name("portrait")
            else:
                if self._board_row.get_parent() is self._portrait_box:
                    self._portrait_box.remove(self._board_row)
                if self._history_box.get_parent() is self._portrait_box:
                    self._portrait_box.remove(self._history_box)
                if self._board_row.get_parent() is not self._landscape_box:
                    self._landscape_box.prepend(self._board_row)
                if self._history_box.get_parent() is not self._landscape_box:
                    self._landscape_box.append(self._history_box)
                self._history_box.set_vexpand(False)
                self._history_box.set_hexpand(False)
                self._content_stack.set_visible_child_name("landscape")

        if w < 820:
            cap_w, hist_w = 88, 130
        elif w < 1024:
            cap_w, hist_w = 110, 165
        else:
            cap_w, hist_w = 140, 200
        self._captured_box.set_size_request(cap_w, -1)
        if self._layout_portrait:
            self._history_box.set_size_request(-1, -1)
        else:
            self._history_box.set_size_request(hist_w, -1)

    def _apply_saved_preferences(self) -> None:
        p = self._prefs
        if "difficulty" in p:
            name = str(p["difficulty"])
            names = list(DIFFICULTY_TO_DEPTH.keys())
            if name in names:
                self.difficulty_dropdown.set_selected(names.index(name))
                self.ai_depth = DIFFICULTY_TO_DEPTH[name]
        if "side" in p:
            side = str(p["side"])
            self.side_dropdown.set_selected(0 if side == "White" else 1)
            self.human_is_white = side == "White"
        if "clock_preset" in p:
            lab = str(p["clock_preset"])
            clock_labels = [opt[0] for opt in CLOCK_OPTIONS]
            if lab in clock_labels:
                self.clock_dropdown.set_selected(clock_labels.index(lab))
        if "theme" in p and str(p["theme"]) in THEMES:
            tname = str(p["theme"])
            names = list(THEMES.keys())
            self.theme_dropdown.set_selected(names.index(tname))
            self._theme = THEMES[tname]
        if "sounds" in p:
            self.sounds_switch.set_active(bool(p["sounds"]))
        self._init_clocks_from_preset()
        self.clock_snapshots = [(self._white_clock_sec, self._black_clock_sec)]

    def _persist_prefs(self) -> None:
        dnames = list(DIFFICULTY_TO_DEPTH.keys())
        di = self.difficulty_dropdown.get_selected()
        difficulty = dnames[di] if 0 <= di < len(dnames) else "Hard"
        side = "White" if self.side_dropdown.get_selected() == 0 else "Black"
        ci = self.clock_dropdown.get_selected()
        clock_labels = [opt[0] for opt in CLOCK_OPTIONS]
        clock_preset = clock_labels[ci] if 0 <= ci < len(clock_labels) else "5+0"
        tnames = list(THEMES.keys())
        ti = self.theme_dropdown.get_selected()
        theme = tnames[ti] if 0 <= ti < len(tnames) else DEFAULT_THEME
        self._prefs = {
            "difficulty": difficulty,
            "side": side,
            "clock_preset": clock_preset,
            "theme": theme,
            "sounds": self.sounds_switch.get_active(),
        }
        save_prefs(self._prefs)

    def _sync_replay_index_to_end(self) -> None:
        self._replay_view_idx = max(0, len(self.state_history) - 1)

    def _board_state_for_ui(self) -> GameState:
        return self.state_history[self._replay_view_idx]

    def _last_move_for_display(self) -> Move | None:
        if self._replay_view_idx <= 0:
            return None
        return self.move_history[self._replay_view_idx - 1]

    def _replay_step(self, delta: int) -> None:
        if len(self.state_history) <= 1:
            return
        n = len(self.state_history)
        self._replay_view_idx = max(0, min(n - 1, self._replay_view_idx + delta))
        self.selected_square = None
        self.hint_move = None
        self._refresh_ui()

    def _replay_confirm_jump(self) -> None:
        if self._replay_view_idx >= len(self.state_history) - 1:
            return
        self._clear_search_analysis()
        self._game_generation += 1
        self._end_announced = False
        self._human_resigned = False
        self._timeout_black_wins = None
        keep = self._replay_view_idx + 1
        self.state_history = self.state_history[:keep]
        self.move_history = self.move_history[: max(0, keep - 1)]
        self.state = self.state_history[-1]
        self.clock_snapshots = self.clock_snapshots[:keep]
        self._white_clock_sec, self._black_clock_sec = self.clock_snapshots[-1]
        self.selected_square = None
        self.hint_move = None
        self.legal_moves = get_legal_moves(self.state)
        self._sync_replay_index_to_end()
        self._last_clock_mono = time.monotonic()
        self._refresh_ui()
        self._persist_prefs()

    def _on_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            self._on_escape()
            return True
        if self._ai_busy:
            return False
        if keyval in (Gdk.KEY_Left, Gdk.KEY_KP_Left):
            self._replay_step(-1)
            return True
        if keyval in (Gdk.KEY_Right, Gdk.KEY_KP_Right):
            self._replay_step(1)
            return True
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_ISO_Enter):
            self._replay_confirm_jump()
            return True
        return False

    def _on_theme_notify(self, *_args: object) -> None:
        names = list(THEMES.keys())
        i = self.theme_dropdown.get_selected()
        if 0 <= i < len(names):
            self._theme = THEMES[names[i]]
            self.board_drawing.queue_draw()
        self._persist_prefs()

    def _on_sounds_active_notify(self, switch: Gtk.Switch, pspec: object) -> None:
        self._persist_prefs()

    def _open_load_fen_dialog(self) -> None:
        dlg = Gtk.Dialog(transient_for=self, modal=True, title="Load FEN")
        dlg.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dlg.add_button("_Load", Gtk.ResponseType.OK)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(10)
        box.set_margin_bottom(12)
        tv = Gtk.TextView()
        tv.set_monospace(True)
        tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        sw = Gtk.ScrolledWindow()
        sw.set_min_content_height(80)
        sw.set_min_content_width(self._dialog_min_width())
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_child(tv)
        buf = tv.get_buffer()
        buf.set_text(state_to_fen(self.state))
        fr = Gtk.Frame(label="FEN string")
        fr.set_child(sw)
        box.append(fr)
        dlg.get_content_area().append(box)

        def on_resp(d: Gtk.Dialog, response: int) -> None:
            if response == Gtk.ResponseType.OK:
                t = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False).strip()
                try:
                    new_state = parse_fen(t)
                except ValueError as exc:
                    err = Gtk.MessageDialog(
                        transient_for=self,
                        modal=True,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.CLOSE,
                        text=str(exc),
                    )
                    err.connect("response", lambda e, _r: e.destroy())
                    err.present()
                else:
                    self._reset_game_from_position(new_state, [], [new_state])
            d.destroy()

        dlg.connect("response", on_resp)
        dlg.present()

    def _open_paste_pgn_dialog(self) -> None:
        dlg = Gtk.Dialog(transient_for=self, modal=True, title="Paste PGN (coordinate moves)")
        dlg.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        dlg.add_button("_Load", Gtk.ResponseType.OK)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(10)
        box.set_margin_bottom(12)
        tv = Gtk.TextView()
        tv.set_monospace(True)
        tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        sw = Gtk.ScrolledWindow()
        sw.set_min_content_height(min(220, max(120, int(self.get_height() * 0.35))))
        sw.set_min_content_width(self._dialog_min_width())
        sw.set_child(tv)
        box.append(Gtk.Label(label="Supports e2e4-style moves (as exported by this app)."))
        box.append(sw)
        dlg.get_content_area().append(box)

        def on_resp(d: Gtk.Dialog, response: int) -> None:
            if response == Gtk.ResponseType.OK:
                buf = tv.get_buffer()
                raw = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
                tokens = extract_coordinate_moves(raw)
                if not tokens:
                    err = Gtk.MessageDialog(
                        transient_for=self,
                        modal=True,
                        message_type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.CLOSE,
                        text="No coordinate moves (e.g. e2e4) found in text.",
                    )
                    err.connect("response", lambda e, _r: e.destroy())
                    err.present()
                else:
                    try:
                        final_s, states, moves = replay_coordinate_moves(tokens)
                    except ValueError as exc:
                        err = Gtk.MessageDialog(
                            transient_for=self,
                            modal=True,
                            message_type=Gtk.MessageType.ERROR,
                            buttons=Gtk.ButtonsType.CLOSE,
                            text=str(exc),
                        )
                        err.connect("response", lambda e, _r: e.destroy())
                        err.present()
                    else:
                        self._reset_game_from_position(final_s, moves, states)
            d.destroy()

        dlg.connect("response", on_resp)
        dlg.present()

    def _reset_game_from_position(
        self,
        new_state: GameState,
        moves: list[Move],
        states: list[GameState],
    ) -> None:
        self._clear_search_analysis()
        self._game_generation += 1
        self._ai_busy = False
        self._end_announced = False
        self._human_resigned = False
        self._timeout_black_wins = None
        self.state = new_state
        self.state_history = states[:]
        self.move_history = moves[:]
        self.selected_square = None
        self.hint_move = None
        self.legal_moves = get_legal_moves(self.state)
        self._init_clocks_from_preset()
        self.clock_snapshots = [(self._white_clock_sec, self._black_clock_sec)]
        for _ in range(len(self.state_history) - 1):
            self.clock_snapshots.append((self._white_clock_sec, self._black_clock_sec))
        self._sync_replay_index_to_end()
        self._last_clock_mono = time.monotonic()
        self._set_controls_enabled(True)
        self._refresh_ui()
        if self.state.white_to_move != self.human_is_white:
            self._after_ms(100, self._play_ai_turn)

    def _on_board_drag_begin(self, gesture: Gtk.GestureDrag, start_x: float, start_y: float) -> None:
        self._drag_start_xy = None
        if self._replay_view_idx != len(self.state_history) - 1:
            return
        if self._ai_busy or self._is_game_finished():
            return
        if self.state.white_to_move != self.human_is_white:
            return
        cell = self._screen_to_cell(start_x, start_y)
        if cell is None:
            return
        row, col = cell
        piece = self.state.board[row][col]
        if piece == "." or piece.isupper() != self.human_is_white:
            return
        self._drag_pick = (row, col)
        self._drag_start_xy = (float(start_x), float(start_y))
        self.selected_square = (row, col)
        self._refresh_ui()

    def _on_board_drag_end(self, gesture: Gtk.GestureDrag, offset_x: float, offset_y: float) -> None:
        if self._drag_pick is None:
            return
        if self._drag_start_xy is None:
            self._drag_pick = None
            return
        start_x, start_y = self._drag_start_xy
        end_x = start_x + offset_x
        end_y = start_y + offset_y
        end_cell = self._screen_to_cell(end_x, end_y)
        self._drag_pick = None
        self._drag_start_xy = None
        if end_cell is None:
            self.selected_square = None
            self._refresh_ui()
            return
        sr, sc = self.selected_square if self.selected_square else (-1, -1)
        er, ec = end_cell
        if (sr, sc) == (er, ec):
            self._refresh_ui()
            return
        self._try_move_from_to(sr, sc, er, ec)

    def _screen_to_cell(self, x: float, y: float) -> tuple[int, int] | None:
        x -= self._board_render_ox
        y -= self._board_render_oy
        s = self._board_render_scale
        if s <= 0:
            return None
        x /= s
        y /= s
        xb = x - self.margin_left
        dr = int(y // self.square_size)
        dc = int(xb // self.square_size)
        if xb < 0 or y < 0 or not (0 <= dr < 8 and 0 <= dc < 8):
            return None
        return self._display_to_board(dr, dc)

    def _try_move_from_to(self, sr: int, sc: int, er: int, ec: int) -> None:
        candidates = [
            m
            for m in self.legal_moves
            if m.start_row == sr and m.start_col == sc and m.end_row == er and m.end_col == ec
        ]
        if not candidates:
            self.selected_square = None
            self._refresh_ui()
            return
        if len(candidates) > 1 and all(m.promotion is not None for m in candidates):
            self._open_promotion_dialog(candidates)
            return
        mv = candidates[0]
        for m in candidates:
            if m.promotion == "Q":
                mv = m
                break
        self._apply_human_move(mv)

    def _play_feedback(self, kind: str) -> None:
        if not self.sounds_switch.get_active():
            return
        fname = {"move": "move.wav", "capture": "capture.wav", "check": "check.wav", "end": "end.wav"}.get(kind)
        path = Path(__file__).resolve().parent / "sounds" / fname if fname else None
        if path is not None and path.is_file():
            if os.name == "nt":
                try:
                    import winsound

                    winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                    return
                except (RuntimeError, OSError):
                    pass
            player = shutil.which("paplay") or shutil.which("pw-play")
            if player and fname:
                try:
                    subprocess.Popen(
                        [player, str(path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return
                except OSError:
                    pass
        disp = Gdk.Display.get_default()
        if disp is None:
            return

        def beep_once() -> bool:
            disp.beep()
            return False

        def beep_twice() -> bool:
            disp.beep()
            GLib.timeout_add(70, beep_once)
            return False

        if kind == "move":
            disp.beep()
        elif kind == "capture":
            disp.beep()
            GLib.timeout_add(70, beep_once)
        elif kind == "check":
            disp.beep()
            GLib.timeout_add(55, beep_once)
            GLib.timeout_add(110, beep_once)
        elif kind == "end":
            GLib.timeout_add(0, beep_twice)

    def _maybe_play_move_sounds(self, move: Move, state_before: GameState) -> None:
        cap = state_before.board[move.end_row][move.end_col] != "." or move.is_en_passant
        if cap:
            self._play_feedback("capture")
        else:
            self._play_feedback("move")
        if is_in_check(self.state, self.state.white_to_move):
            self._play_feedback("check")

    def _on_close_request(self, *_args: object) -> bool:
        self._persist_prefs()
        self._remove_clock_timer()
        return False

    def _remove_clock_timer(self) -> None:
        if self._clock_tick_source_id is not None:
            GLib.source_remove(self._clock_tick_source_id)
            self._clock_tick_source_id = None

    def _restart_clock_timer(self) -> None:
        self._remove_clock_timer()
        self._last_clock_mono = time.monotonic()
        self._clock_tick_source_id = GLib.timeout_add(100, self._on_clock_tick_ms)

    def _on_clock_tick_ms(self) -> bool:
        now = time.monotonic()
        dt = now - self._last_clock_mono
        self._last_clock_mono = now

        if self._clocks_should_tick():
            if self.state.white_to_move:
                self._white_clock_sec -= dt
                if self._white_clock_sec <= 0:
                    self._white_clock_sec = 0.0
                    self._flag_timeout(black_wins=True)
            else:
                self._black_clock_sec -= dt
                if self._black_clock_sec <= 0:
                    self._black_clock_sec = 0.0
                    self._flag_timeout(black_wins=False)

        self._update_clock_labels()
        return True

    def _clocks_should_tick(self) -> bool:
        if not self._clocks_enabled:
            return False
        if self._timeout_black_wins is not None or self._human_resigned:
            return False
        if self._end_announced:
            return False
        return True

    def _init_clocks_from_preset(self) -> None:
        idx = self.clock_dropdown.get_selected()
        if idx < 0 or idx >= len(CLOCK_OPTIONS):
            idx = 5
        _label, main, inc = CLOCK_OPTIONS[idx]
        if main is None:
            self._clocks_enabled = False
            self._white_clock_sec = 0.0
            self._black_clock_sec = 0.0
            self._clock_increment_sec = 0.0
        else:
            self._clocks_enabled = True
            self._white_clock_sec = float(main)
            self._black_clock_sec = float(main)
            self._clock_increment_sec = float(inc or 0.0)

    def _on_clock_preset_notify(self, *_args: object) -> None:
        if len(self.move_history) == 0 and len(self.state_history) == 1:
            self._init_clocks_from_preset()
            self.clock_snapshots = [(self._white_clock_sec, self._black_clock_sec)]
            self._last_clock_mono = time.monotonic()
            self._update_clock_labels()
        self._persist_prefs()

    @staticmethod
    def _format_clock_display(seconds: float) -> str:
        if seconds <= 0:
            return "0:00"
        if seconds < 10.0:
            return f"{seconds:4.1f}s".strip()
        total = int(seconds + 0.5)
        minutes, sec = divmod(total, 60)
        if minutes >= 60:
            hours, minutes = divmod(minutes, 60)
            return f"{hours}:{minutes:02d}:{sec:02d}"
        return f"{minutes}:{sec:02d}"

    def _update_clock_labels(self) -> None:
        if not self._clocks_enabled:
            self.white_clock_label.set_label("—")
            self.black_clock_label.set_label("—")
            return
        self.white_clock_label.set_label(self._format_clock_display(self._white_clock_sec))
        self.black_clock_label.set_label(self._format_clock_display(self._black_clock_sec))

    def _record_clock_after_move(self, mover_was_white: bool) -> None:
        if self._clocks_enabled:
            if mover_was_white:
                self._white_clock_sec += self._clock_increment_sec
            else:
                self._black_clock_sec += self._clock_increment_sec
        self.clock_snapshots.append((self._white_clock_sec, self._black_clock_sec))

    def _flag_timeout(self, black_wins: bool) -> None:
        if self._timeout_black_wins is not None or not self._clocks_enabled:
            return
        self._game_generation += 1
        self._timeout_black_wins = black_wins
        self._end_announced = False
        self._refresh_ui()
        self._is_game_finished()

    # --- GTK / scheduling ---
    def _idle(self, fn: object) -> None:
        def _run() -> bool:
            fn()
            return False

        GLib.idle_add(_run)

    def _after_ms(self, ms: int, fn: object) -> None:

        def _wrap() -> bool:
            fn()
            return False

        GLib.timeout_add(ms, _wrap)

    def _get_difficulty_name(self) -> str:
        names = list(DIFFICULTY_TO_DEPTH.keys())
        i = self.difficulty_dropdown.get_selected()
        if i < 0 or i >= len(names):
            return "Hard"
        return names[i]

    def _clear_search_analysis(self) -> None:
        self._last_search_info = None
        self._last_search_root_white = True
        self.multipv_label.set_label("")

    def _format_search_lines(self, info: SearchInfo, white_to_move_at_root: bool) -> str:
        if not info.multipv:
            return ""
        parts: list[str] = []
        for mv, sc in info.multipv:
            alg = mv.to_algebraic()
            v = sc / 100.0
            if not white_to_move_at_root:
                v = -v
            parts.append(f"{alg} ({v:+.2f})")
        prefix = "Opening book · " if info.nodes == 0 and len(info.multipv) == 1 else "Multi-PV · "
        tail = f" · {info.nodes:,} nodes" if info.nodes else ""
        return prefix + " · ".join(parts) + tail

    def _update_multipv_label(self) -> None:
        if self._last_search_info is None:
            self.multipv_label.set_label("")
            return
        self.multipv_label.set_label(
            self._format_search_lines(self._last_search_info, self._last_search_root_white)
        )

    def _on_difficulty_notify(self, _dropdown: Gtk.DropDown, *_args: object) -> None:
        name = self._get_difficulty_name()
        self.ai_depth = DIFFICULTY_TO_DEPTH.get(name, 5)
        self._update_status_label()
        self._persist_prefs()

    def _on_side_notify(self, _dropdown: Gtk.DropDown, *_args: object) -> None:
        i = self.side_dropdown.get_selected()
        text = "White" if i == 0 else "Black"
        new_side_is_white = text == "White"
        if new_side_is_white == self.human_is_white and len(self.move_history) == 0:
            return
        self.human_is_white = new_side_is_white
        self._restart_game()

    def _on_escape(self) -> None:
        if self._ai_busy:
            return
        if self._replay_view_idx < len(self.state_history) - 1:
            self._sync_replay_index_to_end()
        self.selected_square = None
        self.hint_move = None
        self._refresh_ui()

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.difficulty_dropdown.set_sensitive(enabled)
        self.side_dropdown.set_sensitive(enabled)
        self.undo_button.set_sensitive(enabled)
        self.restart_button.set_sensitive(enabled)
        self._refresh_clock_dropdown_sensitivity()
        self._refresh_resign_button_state()
        self._refresh_hint_button_state()

    def _refresh_clock_dropdown_sensitivity(self) -> None:
        can_change = len(self.move_history) == 0 and not self._ai_busy
        self.clock_dropdown.set_sensitive(can_change)

    def _refresh_resign_button_state(self) -> None:
        can_resign = (
            not self._ai_busy
            and self._terminal_label() is None
            and not self._human_resigned
            and self._timeout_black_wins is None
        )
        self.resign_button.set_sensitive(can_resign)

    def _refresh_hint_button_state(self) -> None:
        can_hint = (
            not self._ai_busy
            and self._terminal_label() is None
            and self.state.white_to_move == self.human_is_white
        )
        self.hint_button.set_sensitive(can_hint)

    def _position_key(self, state: GameState) -> tuple:
        board_tuple = tuple("".join(row) for row in state.board)
        cr = state.castling_rights
        return (
            board_tuple,
            state.white_to_move,
            cr.wk,
            cr.wq,
            cr.bk,
            cr.bq,
            state.en_passant_target,
        )

    def _is_threefold_repetition(self) -> bool:
        counts: Counter[tuple] = Counter()
        for past_state in self.state_history:
            key = self._position_key(past_state)
            counts[key] += 1
            if counts[key] >= 3:
                return True
        return False

    def _draw_rule_reason(self) -> str | None:
        if self.state.halfmove_clock >= 100:
            return "50-move rule"
        if has_insufficient_material(self.state):
            return "insufficient material"
        if self._is_threefold_repetition():
            return "threefold repetition"
        return None

    def _terminal_label(self) -> str | None:
        if self._human_resigned:
            if self.human_is_white:
                return "Resignation - Black wins"
            return "Resignation - White wins"

        if self._timeout_black_wins is not None:
            if self._timeout_black_wins:
                return "Time out - Black wins"
            return "Time out - White wins"

        status = get_game_status(self.state)
        if status == "checkmate":
            winner = "Black" if self.state.white_to_move else "White"
            return f"Checkmate - {winner} wins"
        if status == "stalemate":
            return "Stalemate - Draw"
        reason = self._draw_rule_reason()
        if reason is not None:
            return f"Draw - {reason}"
        return None

    def _pgn_result(self) -> str:
        terminal = self._terminal_label()
        if terminal is None:
            return "*"
        if "White wins" in terminal:
            return "1-0"
        if "Black wins" in terminal:
            return "0-1"
        return "1/2-1/2"

    def _pgn_player_names(self) -> tuple[str, str]:
        if self.human_is_white:
            return "Human", "Engine"
        return "Engine", "Human"

    def _pgn_time_control(self) -> str | None:
        if not self._clocks_enabled:
            return None
        idx = self.clock_dropdown.get_selected()
        if idx < 0 or idx >= len(CLOCK_OPTIONS):
            return None
        _label, main, inc = CLOCK_OPTIONS[idx]
        if main is None:
            return None
        i_sec = int(round(inc or 0.0))
        return f"{int(round(main))}+{i_sec}"

    def _copy_fen_to_clipboard(self) -> None:
        fen = state_to_fen(self.state)
        _set_clipboard_text(self, fen)
        self.status_label.set_label("FEN copied to clipboard.")

    def _copy_pgn_to_clipboard(self) -> None:
        white_name, black_name = self._pgn_player_names()
        text = build_pgn(
            self.move_history,
            result=self._pgn_result(),
            white_name=white_name,
            black_name=black_name,
            time_control=self._pgn_time_control(),
        )
        _set_clipboard_text(self, text)
        self.status_label.set_label("PGN copied to clipboard.")

    def _save_pgn_to_file(self) -> None:
        white_name, black_name = self._pgn_player_names()
        text = build_pgn(
            self.move_history,
            result=self._pgn_result(),
            white_name=white_name,
            black_name=black_name,
            time_control=self._pgn_time_control(),
        )
        dialog = Gtk.FileChooserNative(
            title="Save game as PGN",
            transient_for=self,
            action=Gtk.FileChooserAction.SAVE,
            accept_label="_Save",
            cancel_label="_Cancel",
        )

        def on_response(native: Gtk.FileChooserNative, response: int) -> None:
            self._on_save_pgn_response(native, response, text)

        dialog.connect("response", on_response)
        dialog.show()

    def _on_save_pgn_response(self, native: Gtk.FileChooserNative, response: int, text: str) -> None:
        if response != Gtk.ResponseType.ACCEPT:
            native.destroy()
            return
        gfile = native.get_file()
        native.destroy()
        if gfile is None:
            return
        path = gfile.get_path()
        if path is None:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as exc:
            err = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CLOSE,
                text=f"Could not save file:\n{exc}",
            )
            err.connect("response", lambda d, _rid: d.destroy())
            err.present()
            return
        self.status_label.set_label(f"Saved PGN to {path}")

    def _resign_game(self) -> None:
        if self._ai_busy or self._terminal_label() is not None or self._human_resigned:
            return
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Resign this game? You will lose.",
        )

        def on_response(dlg: Gtk.MessageDialog, response: int) -> None:
            dlg.destroy()
            if response == Gtk.ResponseType.YES:
                self._game_generation += 1
                self._human_resigned = True
                self._end_announced = False
                self._refresh_ui()
                self._is_game_finished()

        dialog.connect("response", on_response)
        dialog.present()

    # --- Board geometry ---
    def _display_to_board(self, display_row: int, display_col: int) -> tuple[int, int]:
        if self.human_is_white:
            return display_row, display_col
        return 7 - display_row, 7 - display_col

    def _board_to_display(self, row: int, col: int) -> tuple[int, int]:
        if self.human_is_white:
            return row, col
        return 7 - row, 7 - col

    def _square_screen_xy(self, row: int, col: int) -> tuple[float, float]:
        display_row, display_col = self._board_to_display(row, col)
        return (
            self.margin_left + display_col * self.square_size,
            display_row * self.square_size,
        )

    def _on_board_pressed(
        self,
        gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
    ) -> None:
        if self._replay_view_idx != len(self.state_history) - 1:
            return
        if self._ai_busy or self._is_game_finished():
            return
        if self.state.white_to_move != self.human_is_white:
            return

        cell = self._screen_to_cell(x, y)
        if cell is None:
            return
        row, col = cell

        clicked_piece = self.state.board[row][col]
        if self.selected_square is None:
            if clicked_piece != "." and clicked_piece.isupper() == self.human_is_white:
                self.selected_square = (row, col)
                self._refresh_ui()
            return

        start_row, start_col = self.selected_square
        candidates = [
            m
            for m in self.legal_moves
            if m.start_row == start_row
            and m.start_col == start_col
            and m.end_row == row
            and m.end_col == col
        ]

        if not candidates:
            if clicked_piece != "." and clicked_piece.isupper() == self.human_is_white:
                self.selected_square = (row, col)
            else:
                self.selected_square = None
            self._refresh_ui()
            return

        if len(candidates) > 1 and all(m.promotion is not None for m in candidates):
            self._open_promotion_dialog(candidates)
            return

        move = candidates[0]
        for m in candidates:
            if m.promotion == "Q":
                move = m
                break
        self._apply_human_move(move)

    def _open_promotion_dialog(self, candidates: list[Move]) -> None:
        dialog = Gtk.Dialog()
        dialog.set_transient_for(self)
        dialog.set_modal(True)
        dialog.set_title("Promote pawn")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_start(14)
        box.set_margin_end(14)
        box.set_margin_top(10)
        box.set_margin_bottom(14)
        labels = [("Queen", "Q"), ("Rook", "R"), ("Bishop", "B"), ("Knight", "N")]

        def choose(_btn: Gtk.Button, code: str) -> None:
            chosen: Move | None = None
            for mv in candidates:
                if mv.promotion == code:
                    chosen = mv
                    break
            dialog.destroy()
            if chosen is not None:
                self._apply_human_move(chosen)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda _b: dialog.destroy())
        box.append(cancel)

        for name, code in labels:
            sym = PIECE_TO_UNICODE[code if self.human_is_white else code.lower()]
            b = Gtk.Button(label=f"{sym} {name}")
            b.connect("clicked", choose, code)
            box.append(b)

        dialog.get_content_area().append(box)
        dialog.present()

    def _apply_human_move(self, move: Move) -> None:
        self._clear_search_analysis()
        mover_white = self.state.white_to_move
        before = self.state
        self.state = self.state.apply_move(move)
        self.state_history.append(self.state)
        self.move_history.append(move)
        self._record_clock_after_move(mover_white)
        self._maybe_play_move_sounds(move, before)
        self.selected_square = None
        self.hint_move = None
        self.legal_moves = get_legal_moves(self.state)
        self._sync_replay_index_to_end()
        self._refresh_ui()
        if not self._is_game_finished():
            self._after_ms(100, self._play_ai_turn)

    def _show_hint(self) -> None:
        if self._ai_busy:
            return
        if get_game_status(self.state) != "ongoing":
            return
        if self.state.white_to_move != self.human_is_white:
            return

        state_snapshot = self.state
        depth = self.ai_depth
        gen = self._game_generation

        self._ai_busy = True
        self._set_controls_enabled(False)
        self.status_label.set_label(f"Computing hint… ({self._get_difficulty_name()})")

        def run_hint() -> None:
            mv, info = pick_move_with_analysis(state_snapshot, depth, 3)

            def finish() -> None:
                self._finish_hint(mv, gen, info, state_snapshot.white_to_move)

            self._idle(finish)

        threading.Thread(target=run_hint, daemon=True).start()

    def _finish_hint(
        self,
        move: Move | None,
        generation: int,
        search_info: SearchInfo | None = None,
        root_white_to_move: bool = True,
    ) -> None:
        self._ai_busy = False
        self._set_controls_enabled(True)
        if generation != self._game_generation:
            self._clear_search_analysis()
            self._refresh_ui()
            return
        self.hint_move = move
        if search_info is not None:
            self._last_search_info = search_info
            self._last_search_root_white = root_white_to_move
            self._update_multipv_label()
        self._refresh_ui()

    def _undo_last_turn(self) -> None:
        if self._ai_busy:
            return
        self._clear_search_analysis()
        if len(self.state_history) <= 1:
            return

        self._game_generation += 1
        self._end_announced = False
        self._human_resigned = False
        self._timeout_black_wins = None

        steps = 2 if self.state.white_to_move == self.human_is_white else 1
        for _ in range(steps):
            if len(self.state_history) <= 1:
                break
            self.state_history.pop()
            if len(self.clock_snapshots) > 1:
                self.clock_snapshots.pop()

        self.state = self.state_history[-1]
        self._white_clock_sec, self._black_clock_sec = self.clock_snapshots[-1]
        self.move_history = self.move_history[: len(self.state_history) - 1]
        self.selected_square = None
        self.hint_move = None
        self.legal_moves = get_legal_moves(self.state)
        self._sync_replay_index_to_end()
        self._refresh_ui()

    def _restart_game(self) -> None:
        self._clear_search_analysis()
        self._game_generation += 1
        self._ai_busy = False
        self._end_announced = False
        self._human_resigned = False
        self._timeout_black_wins = None
        self._set_controls_enabled(True)
        self.state = GameState.initial()
        self.state_history = [self.state]
        self.move_history = []
        self._init_clocks_from_preset()
        self.clock_snapshots = [(self._white_clock_sec, self._black_clock_sec)]
        self._last_clock_mono = time.monotonic()
        self.selected_square = None
        self.hint_move = None
        self.legal_moves = get_legal_moves(self.state)
        self._sync_replay_index_to_end()
        self._refresh_ui()
        self._persist_prefs()
        if self.state.white_to_move != self.human_is_white:
            self._after_ms(100, self._play_ai_turn)

    def _play_ai_turn(self) -> None:
        if self._is_game_finished():
            return
        if self.state.white_to_move == self.human_is_white:
            return

        state_snapshot = self.state
        depth = self.ai_depth
        gen = self._game_generation

        self._ai_busy = True
        self._set_controls_enabled(False)
        self._update_status_label()

        def run_ai() -> None:
            mv, info = pick_move_with_analysis(state_snapshot, depth, 3)

            def finish() -> None:
                self._finish_ai_turn(mv, gen, info, state_snapshot.white_to_move)

            self._idle(finish)

        threading.Thread(target=run_ai, daemon=True).start()

    def _finish_ai_turn(
        self,
        ai_move: Move | None,
        generation: int,
        search_info: SearchInfo | None = None,
        root_white_to_move: bool = True,
    ) -> None:
        self._ai_busy = False
        self._set_controls_enabled(True)

        if generation != self._game_generation:
            self._clear_search_analysis()
            self._refresh_ui()
            return

        if self._is_game_finished():
            self._clear_search_analysis()
            self._refresh_ui()
            return
        if self.state.white_to_move == self.human_is_white:
            self._clear_search_analysis()
            self._refresh_ui()
            return

        if ai_move is None:
            self._clear_search_analysis()
            self._refresh_ui()
            return

        if search_info is not None:
            self._last_search_info = search_info
            self._last_search_root_white = root_white_to_move
            self._update_multipv_label()

        before = self.state
        mover_white = before.white_to_move
        self.state = before.apply_move(ai_move)
        self.state_history.append(self.state)
        self.move_history.append(ai_move)
        self._record_clock_after_move(mover_white)
        self._maybe_play_move_sounds(ai_move, before)
        self.legal_moves = get_legal_moves(self.state)
        self._sync_replay_index_to_end()
        self._refresh_ui()
        self._is_game_finished()

    def _refresh_ui(self) -> None:
        self.board_drawing.queue_draw()
        self.eval_drawing.queue_draw()
        self._update_move_history()
        self._update_captured_panel()
        self._update_clock_labels()
        self._update_status_label()
        self._refresh_clock_dropdown_sensitivity()
        self._refresh_resign_button_state()
        self._refresh_hint_button_state()

    def _board_counts(self, state: GameState) -> tuple[Counter[str], Counter[str]]:
        white = Counter()
        black = Counter()
        for row in state.board:
            for cell in row:
                if cell == ".":
                    continue
                if cell.isupper():
                    white[cell] += 1
                else:
                    black[cell] += 1
        return white, black

    def _format_captured_line(self, lost: Counter[str], for_white_symbols: bool) -> str:
        parts: list[str] = []
        for upper_sym, lower_sym in _CAPTURE_DISPLAY_ORDER:
            sym = upper_sym if for_white_symbols else lower_sym
            count = lost[sym]
            parts.extend([PIECE_TO_UNICODE[sym]] * count)
        return " ".join(parts) if parts else "—"

    def _update_captured_panel(self) -> None:
        white_on_board, black_on_board = self._board_counts(self.state)
        lost_white = _INITIAL_WHITE_PIECES - white_on_board
        lost_black = _INITIAL_BLACK_PIECES - black_on_board

        balance_cp = 0
        for row in self.state.board:
            for cell in row:
                if cell == ".":
                    continue
                v = PIECE_VALUES[cell.lower()]
                balance_cp += v if cell.isupper() else -v

        pawns = balance_cp / 100.0
        if abs(pawns) < 0.05:
            bal_text = "Even"
        else:
            bal_text = f"{'White' if balance_cp > 0 else 'Black'} +{abs(pawns):.1f} (pawns)"

        self.captured_balance_label.set_label(f"Balance: {bal_text}")
        self.captured_white_label.set_label(self._format_captured_line(lost_white, True))
        self.captured_black_label.set_label(self._format_captured_line(lost_black, False))

    def _update_move_history(self) -> None:
        buf = self.history_view.get_buffer()
        lines: list[str] = []
        for index in range(0, len(self.move_history), 2):
            turn_number = (index // 2) + 1
            white_move = self.move_history[index].to_algebraic()
            black_move = ""
            if index + 1 < len(self.move_history):
                black_move = self.move_history[index + 1].to_algebraic()
            lines.append(f"{turn_number}. {white_move} {black_move}".strip())
        buf.set_text("\n".join(lines))
        if buf.get_start_iter().equal(buf.get_end_iter()):
            return
        end = buf.get_end_iter()
        mark = buf.create_mark("end", end, False)
        self.history_view.scroll_to_mark(mark, 0.0, False, 0.0, 1.0)

    def _update_status_label(self) -> None:
        if self._ai_busy:
            self.status_label.set_label(f"AI thinking… ({self._get_difficulty_name()})")
            return

        if self._replay_view_idx < len(self.state_history) - 1:
            self.status_label.set_label(
                f"Replay {self._replay_view_idx + 1}/{len(self.state_history)} — ←/→ Enter jump — Esc live"
            )
            return

        terminal = self._terminal_label()
        if terminal is not None:
            self.status_label.set_label(terminal)
            return

        side_to_move = "White" if self.state.white_to_move else "Black"
        difficulty = self._get_difficulty_name()
        if is_in_check(self.state, self.state.white_to_move):
            self.status_label.set_label(f"{side_to_move} to move - Check! (AI: {difficulty})")
        else:
            self.status_label.set_label(f"{side_to_move} to move (AI: {difficulty})")

    def _is_game_finished(self) -> bool:
        terminal = self._terminal_label()
        if terminal is None:
            return False
        if not self._end_announced:
            self._end_announced = True
            self._play_feedback("end")
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text=terminal + ".",
            )
            dialog.connect("response", lambda d, _r: d.destroy())
            dialog.present()
        return True

    def _draw_piece(self, cr: object, piece: str, cx: float, cy: float) -> None:
        layout = PangoCairo.create_layout(cr)
        layout.set_text(PIECE_TO_UNICODE[piece], -1)
        desc = Pango.FontDescription.from_string(self._theme.piece_font)
        layout.set_font_description(desc)
        layout.set_alignment(Pango.Alignment.CENTER)
        width, height = layout.get_pixel_size()
        cr.save()
        cr.translate(cx - width / 2, cy - height / 2)
        cr.set_source_rgb(*self._theme.piece_rgb)
        PangoCairo.show_layout(cr, layout)
        cr.restore()

    def _draw_board_canvas(self, _area: Gtk.DrawingArea, cr: object, width: int, height: int, _data: object) -> None:
        if width < 2 or height < 2:
            return

        scale = min(width / self.canvas_width, height / self.canvas_height)
        ox = (width - self.canvas_width * scale) / 2.0
        oy = (height - self.canvas_height * scale) / 2.0
        self._board_render_scale = scale
        self._board_render_ox = ox
        self._board_render_oy = oy

        cr.set_source_rgb(0.18, 0.18, 0.19)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        cr.save()
        cr.translate(ox, oy)
        cr.scale(scale, scale)

        cr.set_source_rgb(0.95, 0.93, 0.89)
        cr.rectangle(0, 0, self.canvas_width, self.canvas_height)
        cr.fill()

        light = self._theme.light_sq
        dark = self._theme.dark_sq
        selected_color = self._theme.selected
        move_hint_color = self._theme.move_hint
        last_move_light = self._theme.last_light
        last_move_dark = self._theme.last_dark
        hint_light = self._theme.hint_light
        hint_dark = self._theme.hint_dark
        label_rgb = (0.267, 0.267, 0.267)

        bs = self._board_state_for_ui()
        at_live = self._replay_view_idx == len(self.state_history) - 1
        ui_selection = self.selected_square if at_live else None

        highlighted_targets: set[tuple[int, int]] = set()
        if at_live and ui_selection is not None:
            sr, sc = ui_selection
            highlighted_targets = {
                (m.end_row, m.end_col)
                for m in self.legal_moves
                if m.start_row == sr and m.start_col == sc
            }

        last_move_squares: set[tuple[int, int]] = set()
        lm = self._last_move_for_display()
        if lm is not None:
            last_move_squares = {(lm.start_row, lm.start_col), (lm.end_row, lm.end_col)}

        hint_squares: set[tuple[int, int]] = set()
        if at_live and self.hint_move is not None:
            hint_squares = {
                (self.hint_move.start_row, self.hint_move.start_col),
                (self.hint_move.end_row, self.hint_move.end_col),
            }

        for row in range(8):
            for col in range(8):
                x1, y1 = self._square_screen_xy(row, col)
                x2 = x1 + self.square_size
                y2 = y1 + self.square_size
                is_light = (row + col) % 2 == 0
                rgb = light if is_light else dark

                if (row, col) in last_move_squares:
                    rgb = last_move_light if is_light else last_move_dark
                if (row, col) in hint_squares:
                    rgb = hint_light if is_light else hint_dark
                if ui_selection == (row, col):
                    rgb = selected_color
                elif (row, col) in highlighted_targets:
                    rgb = move_hint_color

                cr.set_source_rgb(*rgb)
                cr.rectangle(x1, y1, self.square_size, self.square_size)
                cr.fill()

        for row in range(8):
            for col in range(8):
                piece = bs.board[row][col]
                if piece == ".":
                    continue
                x1, y1 = self._square_screen_xy(row, col)
                cx = x1 + self.square_size / 2
                cy = y1 + self.square_size / 2
                self._draw_piece(cr, piece, cx, cy)

        ox = self.margin_left
        for display_row in range(8):
            actual_row = display_row if self.human_is_white else 7 - display_row
            rank = str(8 - actual_row)
            layout = PangoCairo.create_layout(cr)
            layout.set_text(rank, -1)
            layout.set_font_description(Pango.FontDescription.from_string("Sans Bold 11"))
            _w, h = layout.get_pixel_size()
            px = ox / 2 - _w / 2
            py = display_row * self.square_size + self.square_size / 2 - h / 2
            cr.save()
            cr.translate(px, py)
            cr.set_source_rgb(*label_rgb)
            PangoCairo.show_layout(cr, layout)
            cr.restore()

        files_y = self.board_size + self.margin_bottom / 2
        for display_col in range(8):
            actual_col = display_col if self.human_is_white else 7 - display_col
            file_letter = chr(ord("a") + actual_col)
            layout = PangoCairo.create_layout(cr)
            layout.set_text(file_letter, -1)
            layout.set_font_description(Pango.FontDescription.from_string("Sans Bold 11"))
            w, h = layout.get_pixel_size()
            cx = ox + display_col * self.square_size + self.square_size / 2
            cr.save()
            cr.translate(cx - w / 2, files_y - h / 2)
            cr.set_source_rgb(*label_rgb)
            PangoCairo.show_layout(cr, layout)
            cr.restore()

        cr.restore()

    def _draw_eval_bar(self, _area: Gtk.DrawingArea, cr: object, width: int, height: int, _data: object) -> None:
        view_state = self._board_state_for_ui()
        at_live = self._replay_view_idx == len(self.state_history) - 1
        terminal = self._terminal_label() if at_live else None
        if terminal is not None and (
            terminal.startswith("Checkmate") or terminal.startswith("Time out")
        ):
            winner_is_white = "White wins" in terminal
            white_frac = 1.0 if winner_is_white else 0.0
            label = "1-0" if winner_is_white else "0-1"
        elif terminal is not None:
            white_frac = 0.5
            label = "½-½"
        else:
            score = evaluate_position(view_state)
            clamped = max(-1500, min(1500, score))
            white_frac = 0.5 + clamped / 3000.0
            pawns = score / 100.0
            label = f"+{pawns:.1f}" if score >= 0 else f"{pawns:.1f}"

        h_total = float(height)
        black_height = int(round((1.0 - white_frac) * h_total))
        cr.set_source_rgb(0.165, 0.165, 0.165)
        cr.rectangle(0, 0, width, black_height)
        cr.fill()
        cr.set_source_rgb(0.941, 0.941, 0.941)
        cr.rectangle(0, black_height, width, h_total - black_height)
        cr.fill()
        cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.set_line_width(1)
        mid = h_total / 2
        cr.move_to(0, mid)
        cr.line_to(width, mid)
        cr.stroke()

        layout = PangoCairo.create_layout(cr)
        layout.set_text(label, -1)
        layout.set_font_description(Pango.FontDescription.from_string("Sans Bold 9"))
        tw, th = layout.get_pixel_size()
        if h_total - black_height >= 14:
            cr.set_source_rgb(0.133, 0.133, 0.133)
            tx = width / 2 - tw / 2
            ty = h_total - 8 - th
        else:
            cr.set_source_rgb(0.933, 0.933, 0.933)
            tx = width / 2 - tw / 2
            ty = 4
        cr.save()
        cr.translate(tx, ty)
        PangoCairo.show_layout(cr, layout)
        cr.restore()


class ChessApplication(Gtk.Application):
    def __init__(self, ai_depth: int = 3) -> None:
        super().__init__(application_id="dev.simplechess.gtk", flags=Gio.ApplicationFlags.FLAGS_NONE)
        self._ai_depth = ai_depth

    def do_activate(self) -> None:
        win = ChessWindow(application=self, ai_depth=self._ai_depth)
        win.present()


def run(ai_depth: int = 3) -> None:
    app = ChessApplication(ai_depth=ai_depth)
    app.run(None)
