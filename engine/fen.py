from __future__ import annotations

import re
from typing import Optional

from .state import CastlingRights, GameState


def state_to_fen(state: GameState) -> str:
    ranks: list[str] = []
    for row in range(8):
        empty_run = 0
        chars: list[str] = []
        for col in range(8):
            piece = state.board[row][col]
            if piece == ".":
                empty_run += 1
            else:
                if empty_run:
                    chars.append(str(empty_run))
                    empty_run = 0
                chars.append(piece)
        if empty_run:
            chars.append(str(empty_run))
        ranks.append("".join(chars))

    placement = "/".join(ranks)
    side = "w" if state.white_to_move else "b"
    castling = _castling_fen(state.castling_rights)
    ep = _en_passant_fen(state)
    half = str(state.halfmove_clock)
    full = str(state.fullmove_number)
    return " ".join((placement, side, castling, ep, half, full))


def parse_fen(fen: str) -> GameState:
    fields = fen.strip().split()
    if len(fields) < 4:
        raise ValueError("FEN must have at least 4 space-separated fields")
    placement, side, castling, ep_field = fields[:4]
    halfmove = int(fields[4]) if len(fields) > 4 else 0
    fullmove = int(fields[5]) if len(fields) > 5 else 1
    if halfmove < 0 or fullmove < 1:
        raise ValueError("Invalid halfmove or fullmove number")

    board = _parse_placement(placement)
    if side not in ("w", "b"):
        raise ValueError("Side to move must be w or b")
    white_to_move = side == "w"
    rights = _parse_castling_field(castling)
    ep = _parse_en_passant_field(ep_field)

    return GameState(
        board=board,
        white_to_move=white_to_move,
        castling_rights=rights,
        en_passant_target=ep,
        halfmove_clock=halfmove,
        fullmove_number=fullmove,
    )


def _parse_placement(placement: str) -> list[list[str]]:
    rank_strs = placement.split("/")
    if len(rank_strs) != 8:
        raise ValueError("FEN placement must have 8 ranks separated by '/'")
    board: list[list[str]] = []
    for rs in rank_strs:
        row: list[str] = []
        for ch in rs:
            if ch.isdigit():
                n = int(ch)
                if not 1 <= n <= 8:
                    raise ValueError(f"Invalid empty-square run: {n}")
                row.extend(["."] * n)
            elif ch in "pnbrqkPNBRQK":
                row.append(ch)
            else:
                raise ValueError(f"Invalid piece or symbol in FEN: {ch!r}")
        if len(row) != 8:
            raise ValueError(f"Rank has {len(row)} files, expected 8")
        board.append(row)
    return board


def _parse_castling_field(castling: str) -> CastlingRights:
    if castling == "-":
        return CastlingRights(False, False, False, False)
    if not re.fullmatch(r"[KQkq]+", castling):
        raise ValueError("Invalid castling field")
    return CastlingRights(
        "K" in castling,
        "Q" in castling,
        "k" in castling,
        "q" in castling,
    )


def _parse_en_passant_field(ep_field: str) -> Optional[tuple[int, int]]:
    if ep_field == "-":
        return None
    if len(ep_field) != 2:
        raise ValueError("Invalid en passant square")
    file_letter, rank_char = ep_field[0], ep_field[1]
    if file_letter not in "abcdefgh" or rank_char not in "12345678":
        raise ValueError("Invalid en passant square")
    col = ord(file_letter) - ord("a")
    row = 8 - int(rank_char)
    return row, col


def _castling_fen(rights: CastlingRights) -> str:
    parts: list[str] = []
    if rights.wk:
        parts.append("K")
    if rights.wq:
        parts.append("Q")
    if rights.bk:
        parts.append("k")
    if rights.bq:
        parts.append("q")
    return "".join(parts) if parts else "-"


def _en_passant_fen(state: GameState) -> str:
    if state.en_passant_target is None:
        return "-"
    row, col = state.en_passant_target
    file_letter = chr(ord("a") + col)
    rank_digit = str(8 - row)
    return f"{file_letter}{rank_digit}"
