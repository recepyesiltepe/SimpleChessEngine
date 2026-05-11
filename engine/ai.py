from __future__ import annotations

from math import inf
from typing import Optional

from .state import GameState, Move, get_game_status, get_legal_moves


MATE_SCORE = 100_000
PIECE_VALUES = {
    "p": 100,
    "n": 320,
    "b": 330,
    "r": 500,
    "q": 900,
    "k": 0,
}


def choose_best_move(state: GameState, depth: int = 3) -> Optional[Move]:
    legal_moves = get_legal_moves(state)
    if not legal_moves:
        return None

    ordered_moves = _order_moves(state, legal_moves)
    if state.white_to_move:
        best_score = -inf
        best_move = ordered_moves[0]
        for move in ordered_moves:
            score = _minimax(state.apply_move(move), depth - 1, -inf, inf)
            if score > best_score:
                best_score = score
                best_move = move
        return best_move

    best_score = inf
    best_move = ordered_moves[0]
    for move in ordered_moves:
        score = _minimax(state.apply_move(move), depth - 1, -inf, inf)
        if score < best_score:
            best_score = score
            best_move = move
    return best_move


def _minimax(state: GameState, depth: int, alpha: float, beta: float) -> float:
    status = get_game_status(state)
    if status != "ongoing":
        if status == "stalemate":
            return 0
        return -MATE_SCORE if state.white_to_move else MATE_SCORE

    if depth == 0:
        return _evaluate_position(state)

    legal_moves = get_legal_moves(state)
    ordered_moves = _order_moves(state, legal_moves)

    if state.white_to_move:
        best_score = -inf
        for move in ordered_moves:
            score = _minimax(state.apply_move(move), depth - 1, alpha, beta)
            best_score = max(best_score, score)
            alpha = max(alpha, score)
            if beta <= alpha:
                break
        return best_score

    best_score = inf
    for move in ordered_moves:
        score = _minimax(state.apply_move(move), depth - 1, alpha, beta)
        best_score = min(best_score, score)
        beta = min(beta, score)
        if beta <= alpha:
            break
    return best_score


def _evaluate_position(state: GameState) -> int:
    score = 0
    for row in state.board:
        for piece in row:
            if piece == ".":
                continue
            value = PIECE_VALUES[piece.lower()]
            score += value if piece.isupper() else -value
    return score


def evaluate_position(state: GameState) -> int:
    return _evaluate_position(state)


def _order_moves(state: GameState, moves: list[Move]) -> list[Move]:
    def priority(move: Move) -> int:
        captured_piece = "."
        moving_piece = state.board[move.start_row][move.start_col]
        if move.is_en_passant:
            capture_row = move.end_row + 1 if moving_piece.isupper() else move.end_row - 1
            captured_piece = state.board[capture_row][move.end_col]
        else:
            captured_piece = state.board[move.end_row][move.end_col]

        score = 0
        if captured_piece != ".":
            score += 10 * PIECE_VALUES[captured_piece.lower()] - PIECE_VALUES[moving_piece.lower()]
        if move.promotion:
            score += PIECE_VALUES[move.promotion.lower()]
        if move.is_castle:
            score += 25
        return score

    return sorted(moves, key=priority, reverse=True)
