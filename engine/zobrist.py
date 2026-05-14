from __future__ import annotations

import random
from typing import Final

from .state import GameState

_MASK64: Final[int] = (1 << 64) - 1

# Fixed seed so hashes are stable across runs (opening book keys, debugging).
_RNG = random.Random(0x5EED_C0DE)


def _rand64() -> int:
    return _RNG.getrandbits(64) & _MASK64


# 12 piece types: PNBRQK pnbrqk (same order as iteration)
_PIECE_TYPES = "PNBRQKpnbrqk"
_PIECE_INDEX: dict[str, int] = {c: i for i, c in enumerate(_PIECE_TYPES)}

# [piece_type][square_index 0..63]
ZOBRIST_PIECE: list[list[int]] = [[_rand64() for _ in range(64)] for _ in range(12)]
ZOBRIST_SIDE: int = _rand64()
ZOBRIST_CASTLE: tuple[int, int, int, int] = (_rand64(), _rand64(), _rand64(), _rand64())
# en passant file 0 = none, 1..8 = a..h file of ep target square
ZOBRIST_EP_FILE: list[int] = [_rand64() for _ in range(9)]


def zobrist_hash(state: GameState) -> int:
    h = 0
    board = state.board
    for row in range(8):
        for col in range(8):
            p = board[row][col]
            if p == ".":
                continue
            sq = row * 8 + col
            pi = _PIECE_INDEX[p]
            h ^= ZOBRIST_PIECE[pi][sq]
            h &= _MASK64

    if not state.white_to_move:
        h ^= ZOBRIST_SIDE
    r = state.castling_rights
    if r.wk:
        h ^= ZOBRIST_CASTLE[0]
    if r.wq:
        h ^= ZOBRIST_CASTLE[1]
    if r.bk:
        h ^= ZOBRIST_CASTLE[2]
    if r.bq:
        h ^= ZOBRIST_CASTLE[3]

    if state.en_passant_target is not None:
        _er, ec = state.en_passant_target
        h ^= ZOBRIST_EP_FILE[ec + 1]

    return h & _MASK64
