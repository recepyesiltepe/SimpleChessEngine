from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from engine import GameState, Move, choose_best_move, get_game_status, get_legal_moves, is_in_check


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


class ChessApp:
    def __init__(self, root: tk.Tk, ai_depth: int = 3) -> None:
        self.root = root
        self.ai_depth = ai_depth
        self.square_size = 80
        self.board_size = self.square_size * 8
        self.human_is_white = True

        self.state = GameState.initial()
        self.selected_square: tuple[int, int] | None = None
        self.legal_moves: list[Move] = get_legal_moves(self.state)

        controls_frame = tk.Frame(root)
        controls_frame.pack(pady=(8, 4))

        tk.Label(controls_frame, text="Difficulty:").pack(side=tk.LEFT, padx=(0, 6))

        default_difficulty = "Hard"
        for name, depth in DIFFICULTY_TO_DEPTH.items():
            if depth == ai_depth:
                default_difficulty = name
                break

        self.difficulty_var = tk.StringVar(value=default_difficulty)
        difficulty_menu = tk.OptionMenu(
            controls_frame,
            self.difficulty_var,
            *DIFFICULTY_TO_DEPTH.keys(),
            command=self._on_difficulty_change,
        )
        difficulty_menu.config(width=8)
        difficulty_menu.pack(side=tk.LEFT)

        self.canvas = tk.Canvas(root, width=self.board_size, height=self.board_size, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)

        self.status_var = tk.StringVar()
        self.status_label = tk.Label(root, textvariable=self.status_var, font=("Arial", 12))
        self.status_label.pack(pady=8)

        self._refresh_ui()

    def _on_difficulty_change(self, selected_difficulty: str) -> None:
        self.ai_depth = DIFFICULTY_TO_DEPTH[selected_difficulty]
        self._update_status_label()

    def on_click(self, event: tk.Event) -> None:
        if self._is_game_finished():
            return
        if self.state.white_to_move != self.human_is_white:
            return

        col = event.x // self.square_size
        row = event.y // self.square_size
        if not (0 <= row < 8 and 0 <= col < 8):
            return

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
            self.selected_square = None
            self.legal_moves = get_legal_moves(self.state)
            self._refresh_ui()

            if not self._is_game_finished():
                self.root.after(100, self._play_ai_turn)
            return

        if clicked_piece != "." and clicked_piece.isupper() == self.human_is_white:
            self.selected_square = (row, col)
        else:
            self.selected_square = None
        self._refresh_ui()

    def _play_ai_turn(self) -> None:
        if self._is_game_finished():
            return
        if self.state.white_to_move == self.human_is_white:
            return

        ai_move = choose_best_move(self.state, depth=self.ai_depth)
        if ai_move is None:
            self._refresh_ui()
            return

        self.state = self.state.apply_move(ai_move)
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

        for move in candidates:
            if move.promotion == "Q":
                return move
        return candidates[0]

    def _refresh_ui(self) -> None:
        self._draw_board()
        self._draw_pieces()
        self._update_status_label()

    def _draw_board(self) -> None:
        self.canvas.delete("all")
        light = "#F0D9B5"
        dark = "#B58863"
        selected_color = "#E8E36E"
        move_hint_color = "#8BC34A"

        highlighted_targets = set()
        if self.selected_square is not None:
            row, col = self.selected_square
            highlighted_targets = {
                (move.end_row, move.end_col)
                for move in self.legal_moves
                if move.start_row == row and move.start_col == col
            }

        for row in range(8):
            for col in range(8):
                x1 = col * self.square_size
                y1 = row * self.square_size
                x2 = x1 + self.square_size
                y2 = y1 + self.square_size
                color = light if (row + col) % 2 == 0 else dark

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
                x = col * self.square_size + self.square_size // 2
                y = row * self.square_size + self.square_size // 2
                self.canvas.create_text(
                    x,
                    y,
                    text=PIECE_TO_UNICODE[piece],
                    font=("Arial", 40),
                    fill="#111111",
                )

    def _update_status_label(self) -> None:
        side_to_move = "White" if self.state.white_to_move else "Black"
        status = get_game_status(self.state)
        difficulty = self.difficulty_var.get()

        if status == "ongoing":
            if is_in_check(self.state, self.state.white_to_move):
                self.status_var.set(f"{side_to_move} to move - Check! (AI: {difficulty})")
            else:
                self.status_var.set(f"{side_to_move} to move (AI: {difficulty})")
            return

        if status == "checkmate":
            winner = "Black" if self.state.white_to_move else "White"
            self.status_var.set(f"Checkmate - {winner} wins")
            return

        self.status_var.set("Stalemate - Draw")

    def _is_game_finished(self) -> bool:
        status = get_game_status(self.state)
        if status == "ongoing":
            return False

        if status == "checkmate":
            winner = "Black" if self.state.white_to_move else "White"
            messagebox.showinfo("Game Over", f"Checkmate! {winner} wins.")
        else:
            messagebox.showinfo("Game Over", "Stalemate! It's a draw.")
        return True


def run(ai_depth: int = 3) -> None:
    root = tk.Tk()
    root.title("Python Chess Engine - Minimax AI")
    ChessApp(root, ai_depth=ai_depth)
    root.mainloop()
