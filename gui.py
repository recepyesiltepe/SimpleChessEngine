from __future__ import annotations

import threading
from collections import Counter
from tkinter import messagebox

import tkinter as tk

from engine import (
    GameState,
    Move,
    choose_best_move,
    evaluate_position,
    get_game_status,
    get_legal_moves,
    has_insufficient_material,
    is_in_check,
)
from engine.ai import PIECE_VALUES


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
    "Easy": 1,
    "Medium": 2,
    "Hard": 3,
    "Expert": 4,
}

_INITIAL_WHITE_PIECES = Counter(P=8, R=2, N=2, B=2, Q=1, K=1)
_INITIAL_BLACK_PIECES = Counter(p=8, r=2, n=2, b=2, q=1, k=1)

_CAPTURE_DISPLAY_ORDER = (
    ("Q", "q"),
    ("R", "r"),
    ("B", "b"),
    ("N", "n"),
    ("P", "p"),
)


class ChessApp:
    def __init__(self, root: tk.Tk, ai_depth: int = 3) -> None:
        self.root = root
        self.ai_depth = ai_depth
        self.square_size = 80
        self.board_size = self.square_size * 8
        self.margin_left = 28
        self.margin_bottom = 28
        self.canvas_width = self.margin_left + self.board_size
        self.canvas_height = self.board_size + self.margin_bottom
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
        self.eval_bar_width = 28

        controls_frame = tk.Frame(root)
        controls_frame.pack(pady=(8, 4))

        tk.Label(controls_frame, text="Difficulty:").pack(side=tk.LEFT, padx=(0, 6))

        default_difficulty = "Hard"
        for name, depth in DIFFICULTY_TO_DEPTH.items():
            if depth == ai_depth:
                default_difficulty = name
                break

        self.difficulty_var = tk.StringVar(value=default_difficulty)
        self.difficulty_menu = tk.OptionMenu(
            controls_frame,
            self.difficulty_var,
            *DIFFICULTY_TO_DEPTH.keys(),
            command=self._on_difficulty_change,
        )
        self.difficulty_menu.config(width=8)
        self.difficulty_menu.pack(side=tk.LEFT)

        tk.Label(controls_frame, text="Play as:").pack(side=tk.LEFT, padx=(12, 6))
        self.side_var = tk.StringVar(value="White")
        self.side_menu = tk.OptionMenu(
            controls_frame,
            self.side_var,
            "White",
            "Black",
            command=self._on_side_change,
        )
        self.side_menu.config(width=6)
        self.side_menu.pack(side=tk.LEFT)

        self.hint_button = tk.Button(controls_frame, text="Hint", width=8, command=self._show_hint)
        self.hint_button.pack(side=tk.LEFT, padx=(12, 4))
        self.undo_button = tk.Button(controls_frame, text="Undo", width=8, command=self._undo_last_turn)
        self.undo_button.pack(side=tk.LEFT, padx=(4, 4))
        self.restart_button = tk.Button(controls_frame, text="Restart", width=8, command=self._restart_game)
        self.restart_button.pack(side=tk.LEFT)

        content_frame = tk.Frame(root)
        content_frame.pack(padx=8, pady=4)

        captured_frame = tk.Frame(content_frame)
        captured_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        tk.Label(captured_frame, text="Material", font=("Arial", 11, "bold")).pack(anchor="w")
        self.captured_balance_var = tk.StringVar()
        tk.Label(captured_frame, textvariable=self.captured_balance_var, font=("Arial", 10)).pack(anchor="w", pady=(0, 6))
        tk.Label(captured_frame, text="Off board (White)", font=("Arial", 9)).pack(anchor="w")
        self.captured_white_var = tk.StringVar()
        tk.Label(captured_frame, textvariable=self.captured_white_var, font=("Arial", 18), wraplength=120, justify=tk.LEFT).pack(
            anchor="w", pady=(0, 8)
        )
        tk.Label(captured_frame, text="Off board (Black)", font=("Arial", 9)).pack(anchor="w")
        self.captured_black_var = tk.StringVar()
        tk.Label(captured_frame, textvariable=self.captured_black_var, font=("Arial", 18), wraplength=120, justify=tk.LEFT).pack(anchor="w")

        self.eval_bar_canvas = tk.Canvas(
            content_frame,
            width=self.eval_bar_width,
            height=self.board_size,
            highlightthickness=1,
            highlightbackground="#888888",
        )
        self.eval_bar_canvas.pack(side=tk.LEFT, padx=(0, 6))

        self.canvas = tk.Canvas(content_frame, width=self.canvas_width, height=self.canvas_height, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT)
        self.canvas.bind("<Button-1>", self.on_click)

        history_frame = tk.Frame(content_frame)
        history_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))

        tk.Label(history_frame, text="Move History", font=("Arial", 11, "bold")).pack(anchor="w")
        scrollbar = tk.Scrollbar(history_frame, orient=tk.VERTICAL)
        self.history_listbox = tk.Listbox(history_frame, width=24, height=24, yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.history_listbox.yview)
        self.history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        self.status_var = tk.StringVar()
        self.status_label = tk.Label(root, textvariable=self.status_var, font=("Arial", 12))
        self.status_label.pack(pady=8)

        self._refresh_ui()

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.difficulty_menu.config(state=state)
        self.side_menu.config(state=state)
        self.undo_button.config(state=state)
        self.restart_button.config(state=state)
        self._refresh_hint_button_state()

    def _refresh_hint_button_state(self) -> None:
        can_hint = (
            not self._ai_busy
            and self._terminal_label() is None
            and self.state.white_to_move == self.human_is_white
        )
        self.hint_button.config(state=tk.NORMAL if can_hint else tk.DISABLED)

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

    def _on_difficulty_change(self, selected_difficulty: str) -> None:
        self.ai_depth = DIFFICULTY_TO_DEPTH[selected_difficulty]
        self._update_status_label()

    def _on_side_change(self, selected_side: str) -> None:
        new_side_is_white = selected_side == "White"
        if new_side_is_white == self.human_is_white and len(self.move_history) == 0:
            return
        self.human_is_white = new_side_is_white
        self._restart_game()

    def _undo_last_turn(self) -> None:
        if self._ai_busy:
            return
        if len(self.state_history) <= 1:
            return

        self._game_generation += 1
        self._end_announced = False

        steps = 2 if self.state.white_to_move == self.human_is_white else 1
        for _ in range(steps):
            if len(self.state_history) <= 1:
                break
            self.state_history.pop()

        self.state = self.state_history[-1]
        self.move_history = self.move_history[: len(self.state_history) - 1]
        self.selected_square = None
        self.hint_move = None
        self.legal_moves = get_legal_moves(self.state)
        self._refresh_ui()

    def _restart_game(self) -> None:
        self._game_generation += 1
        self._ai_busy = False
        self._end_announced = False
        self._set_controls_enabled(True)
        self.state = GameState.initial()
        self.state_history = [self.state]
        self.move_history = []
        self.selected_square = None
        self.hint_move = None
        self.legal_moves = get_legal_moves(self.state)
        self._refresh_ui()
        if self.state.white_to_move != self.human_is_white:
            self.root.after(100, self._play_ai_turn)

    def _display_to_board(self, display_row: int, display_col: int) -> tuple[int, int]:
        if self.human_is_white:
            return display_row, display_col
        return 7 - display_row, 7 - display_col

    def _board_to_display(self, row: int, col: int) -> tuple[int, int]:
        if self.human_is_white:
            return row, col
        return 7 - row, 7 - col

    def _square_screen_xy(self, row: int, col: int) -> tuple[int, int]:
        display_row, display_col = self._board_to_display(row, col)
        return (
            self.margin_left + display_col * self.square_size,
            display_row * self.square_size,
        )

    def on_click(self, event: tk.Event) -> None:
        if self._ai_busy:
            return
        if self._is_game_finished():
            return
        if self.state.white_to_move != self.human_is_white:
            return

        x_board = event.x - self.margin_left
        display_row = event.y // self.square_size
        display_col = x_board // self.square_size
        if x_board < 0 or event.y < 0 or not (0 <= display_row < 8 and 0 <= display_col < 8):
            return
        row, col = self._display_to_board(display_row, display_col)

        clicked_piece = self.state.board[row][col]
        if self.selected_square is None:
            if clicked_piece != "." and clicked_piece.isupper() == self.human_is_white:
                self.selected_square = (row, col)
                self._refresh_ui()
            return

        start_row, start_col = self.selected_square
        move = self._select_move(start_row, start_col, row, col)

        if move is not None:
            self.state = self.state.apply_move(move)
            self.state_history.append(self.state)
            self.move_history.append(move)
            self.selected_square = None
            self.hint_move = None
            self.legal_moves = get_legal_moves(self.state)
            self._refresh_ui()

            if not self._is_game_finished():
                self.root.after(100, self._play_ai_turn)
            return

        if self.selected_square == (start_row, start_col) and self._has_multiple_promotions(start_row, start_col, row, col):
            self._refresh_ui()
            return

        if clicked_piece != "." and clicked_piece.isupper() == self.human_is_white:
            self.selected_square = (row, col)
        else:
            self.selected_square = None
        self._refresh_ui()

    def _has_multiple_promotions(self, start_row: int, start_col: int, end_row: int, end_col: int) -> bool:
        candidates = [
            m
            for m in self.legal_moves
            if m.start_row == start_row
            and m.start_col == start_col
            and m.end_row == end_row
            and m.end_col == end_col
        ]
        if len(candidates) <= 1:
            return False
        return all(m.promotion is not None for m in candidates)

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
        self.status_var.set(f"Computing hint… ({self.difficulty_var.get()})")

        def run_hint() -> None:
            move = choose_best_move(state_snapshot, depth=depth)
            self.root.after(0, lambda m=move, g=gen: self._finish_hint(m, g))

        threading.Thread(target=run_hint, daemon=True).start()

    def _finish_hint(self, move: Move | None, generation: int) -> None:
        self._ai_busy = False
        self._set_controls_enabled(True)
        if generation != self._game_generation:
            self._refresh_ui()
            return
        self.hint_move = move
        self._refresh_ui()

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
            move = choose_best_move(state_snapshot, depth=depth)
            self.root.after(0, lambda m=move, g=gen: self._finish_ai_turn(m, g))

        threading.Thread(target=run_ai, daemon=True).start()

    def _finish_ai_turn(self, ai_move: Move | None, generation: int) -> None:
        self._ai_busy = False
        self._set_controls_enabled(True)

        if generation != self._game_generation:
            self._refresh_ui()
            return

        if self._is_game_finished():
            self._refresh_ui()
            return
        if self.state.white_to_move == self.human_is_white:
            self._refresh_ui()
            return

        if ai_move is None:
            self._refresh_ui()
            return

        self.state = self.state.apply_move(ai_move)
        self.state_history.append(self.state)
        self.move_history.append(ai_move)
        self.legal_moves = get_legal_moves(self.state)
        self._refresh_ui()
        self._is_game_finished()

    def _select_move(self, start_row: int, start_col: int, end_row: int, end_col: int) -> Move | None:
        candidates = [
            move
            for move in self.legal_moves
            if move.start_row == start_row
            and move.start_col == start_col
            and move.end_row == end_row
            and move.end_col == end_col
        ]
        if not candidates:
            return None

        if len(candidates) > 1 and all(m.promotion is not None for m in candidates):
            return self._pick_promotion_move(candidates)

        for move in candidates:
            if move.promotion == "Q":
                return move
        return candidates[0]

    def _pick_promotion_move(self, candidates: list[Move]) -> Move | None:
        top = tk.Toplevel(self.root)
        top.title("Promote pawn")
        top.transient(self.root)
        top.grab_set()

        chosen: list[Move | None] = [None]

        def pick(piece: str) -> None:
            for mv in candidates:
                if mv.promotion == piece:
                    chosen[0] = mv
                    break
            top.destroy()

        def on_close() -> None:
            top.destroy()

        top.protocol("WM_DELETE_WINDOW", on_close)

        tk.Label(top, text="Choose promotion piece:", padx=14, pady=10).pack()
        btn_frame = tk.Frame(top)
        btn_frame.pack(pady=(0, 14))
        labels = [("Queen", "Q"), ("Rook", "R"), ("Bishop", "B"), ("Knight", "N")]
        for name, code in labels:
            display = PIECE_TO_UNICODE[code if self.human_is_white else code.lower()]
            tk.Button(btn_frame, text=f"{display} {name}", command=lambda c=code: pick(c)).pack(side=tk.LEFT, padx=4)

        top.wait_window()
        return chosen[0]

    def _refresh_ui(self) -> None:
        self._draw_board()
        self._draw_pieces()
        self._draw_coordinates()
        self._draw_eval_bar()
        self._update_move_history()
        self._update_captured_panel()
        self._update_status_label()
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

        self.captured_balance_var.set(f"Balance: {bal_text}")
        self.captured_white_var.set(self._format_captured_line(lost_white, True))
        self.captured_black_var.set(self._format_captured_line(lost_black, False))

    def _update_move_history(self) -> None:
        self.history_listbox.delete(0, tk.END)
        for index in range(0, len(self.move_history), 2):
            turn_number = (index // 2) + 1
            white_move = self.move_history[index].to_algebraic()
            black_move = ""
            if index + 1 < len(self.move_history):
                black_move = self.move_history[index + 1].to_algebraic()
            self.history_listbox.insert(tk.END, f"{turn_number}. {white_move} {black_move}".strip())
        self.history_listbox.yview_moveto(1.0)

    def _draw_board(self) -> None:
        self.canvas.delete("all")
        light = "#F0D9B5"
        dark = "#B58863"
        selected_color = "#E8E36E"
        move_hint_color = "#8BC34A"
        last_move_light = "#F7EC74"
        last_move_dark = "#DAC34B"
        hint_light = "#9EC8FF"
        hint_dark = "#5B86C2"

        highlighted_targets = set()
        if self.selected_square is not None:
            row, col = self.selected_square
            highlighted_targets = {
                (move.end_row, move.end_col)
                for move in self.legal_moves
                if move.start_row == row and move.start_col == col
            }

        last_move_squares: set[tuple[int, int]] = set()
        if self.move_history:
            last_move = self.move_history[-1]
            last_move_squares = {
                (last_move.start_row, last_move.start_col),
                (last_move.end_row, last_move.end_col),
            }

        hint_squares: set[tuple[int, int]] = set()
        if self.hint_move is not None:
            hint_squares = {
                (self.hint_move.start_row, self.hint_move.start_col),
                (self.hint_move.end_row, self.hint_move.end_col),
            }

        for row in range(8):
            for col in range(8):
                x1, y1 = self._square_screen_xy(row, col)
                x2 = x1 + self.square_size
                y2 = y1 + self.square_size
                is_light_square = (row + col) % 2 == 0
                color = light if is_light_square else dark

                if (row, col) in last_move_squares:
                    color = last_move_light if is_light_square else last_move_dark

                if (row, col) in hint_squares:
                    color = hint_light if is_light_square else hint_dark

                if self.selected_square == (row, col):
                    color = selected_color
                elif (row, col) in highlighted_targets:
                    color = move_hint_color

                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline=color)

    def _draw_pieces(self) -> None:
        for row in range(8):
            for col in range(8):
                piece = self.state.board[row][col]
                if piece == ".":
                    continue
                x1, y1 = self._square_screen_xy(row, col)
                x = x1 + self.square_size // 2
                y = y1 + self.square_size // 2
                self.canvas.create_text(
                    x,
                    y,
                    text=PIECE_TO_UNICODE[piece],
                    font=("Arial", 40),
                    fill="#111111",
                )

    def _draw_coordinates(self) -> None:
        ox = self.margin_left
        label_fill = "#444444"
        font_small = ("Arial", 11, "bold")

        for display_row in range(8):
            actual_row = display_row if self.human_is_white else 7 - display_row
            rank = str(8 - actual_row)
            self.canvas.create_text(
                ox // 2,
                display_row * self.square_size + self.square_size // 2,
                text=rank,
                font=font_small,
                fill=label_fill,
            )

        files_y = self.board_size + self.margin_bottom // 2
        for display_col in range(8):
            actual_col = display_col if self.human_is_white else 7 - display_col
            file_letter = chr(ord("a") + actual_col)
            self.canvas.create_text(
                ox + display_col * self.square_size + self.square_size // 2,
                files_y,
                text=file_letter,
                font=font_small,
                fill=label_fill,
            )

    def _update_status_label(self) -> None:
        if self._ai_busy:
            difficulty = self.difficulty_var.get()
            self.status_var.set(f"AI thinking… ({difficulty})")
            return

        terminal = self._terminal_label()
        if terminal is not None:
            self.status_var.set(terminal)
            return

        side_to_move = "White" if self.state.white_to_move else "Black"
        difficulty = self.difficulty_var.get()
        if is_in_check(self.state, self.state.white_to_move):
            self.status_var.set(f"{side_to_move} to move - Check! (AI: {difficulty})")
        else:
            self.status_var.set(f"{side_to_move} to move (AI: {difficulty})")

    def _is_game_finished(self) -> bool:
        terminal = self._terminal_label()
        if terminal is None:
            return False
        if not self._end_announced:
            self._end_announced = True
            messagebox.showinfo("Game Over", terminal + ".")
        return True

    def _draw_eval_bar(self) -> None:
        self.eval_bar_canvas.delete("all")
        width = self.eval_bar_width
        height = self.board_size

        terminal = self._terminal_label()
        if terminal is not None and terminal.startswith("Checkmate"):
            winner_is_white = "White wins" in terminal
            white_frac = 1.0 if winner_is_white else 0.0
            label = "1-0" if winner_is_white else "0-1"
        elif terminal is not None:
            white_frac = 0.5
            label = "½-½"
        else:
            score = evaluate_position(self.state)
            clamped = max(-1500, min(1500, score))
            white_frac = 0.5 + clamped / 3000.0
            pawns = score / 100.0
            label = f"+{pawns:.1f}" if score >= 0 else f"{pawns:.1f}"

        white_height = int(round(white_frac * height))
        black_height = height - white_height

        self.eval_bar_canvas.create_rectangle(0, 0, width, black_height, fill="#2A2A2A", outline="#2A2A2A")
        self.eval_bar_canvas.create_rectangle(0, black_height, width, height, fill="#F0F0F0", outline="#F0F0F0")
        midline = height // 2
        self.eval_bar_canvas.create_line(0, midline, width, midline, fill="#808080")

        if white_height >= 14:
            self.eval_bar_canvas.create_text(
                width // 2,
                height - 8,
                text=label,
                font=("Arial", 9, "bold"),
                fill="#222222",
            )
        else:
            self.eval_bar_canvas.create_text(
                width // 2,
                8,
                text=label,
                font=("Arial", 9, "bold"),
                fill="#EEEEEE",
            )


def run(ai_depth: int = 3) -> None:
    root = tk.Tk()
    root.title("Python Chess Engine - Minimax AI")
    ChessApp(root, ai_depth=ai_depth)
    root.mainloop()
