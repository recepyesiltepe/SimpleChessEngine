from __future__ import annotations

import random
from typing import Final

from .fen import state_to_fen
from .pgn import find_legal_move_matching
from .state import GameState, get_legal_moves

_rng = random.Random(0xB00C)

# Weighted replies: (UCI, weight). Weights need not sum to a specific total.
_BookLine = dict[tuple[str, str, str, str], list[tuple[str, int]]]

_RAW_BOOK: Final[list[tuple[str, list[tuple[str, int]]]]] = [
    # White 1st moves
    ("", [("e2e4", 40), ("d2d4", 35), ("g1f3", 12), ("c2c4", 10), ("b1c3", 3)]),
    # After 1.e4
    ("e2e4", [("e7e5", 35), ("c7c5", 28), ("e7e6", 14), ("c7c6", 6), ("g8f6", 10), ("d7d6", 7)]),
    # After 1.d4
    ("d2d4", [("g8f6", 30), ("d7d5", 35), ("e7e6", 18), ("f7f5", 5), ("d7d6", 7), ("c7c5", 5)]),
    # After 1.Nf3
    ("g1f3", [("d7d5", 40), ("g8f6", 35), ("c7c5", 12), ("e7e6", 8), ("f7f5", 5)]),
    # After 1.c4
    ("c2c4", [("e7e5", 25), ("c7c5", 30), ("g8f6", 25), ("e7e6", 12), ("f7f5", 8)]),
    # After 1.e4 e5
    ("e2e4 e7e5", [("g1f3", 45), ("f2f4", 8), ("b1c3", 35), ("f1c4", 12)]),
    # After 1.e4 c5
    ("e2e4 c7c5", [("g1f3", 50), ("b1c3", 35), ("f2f4", 8), ("c2c3", 7)]),
    # After 1.d4 d5
    ("d2d4 d7d5", [("c2c4", 40), ("e2e3", 25), ("g1f3", 30), ("c1f4", 5)]),
    # After 1.d4 Nf6
    ("d2d4 g8f6", [("c2c4", 45), ("g1f3", 40), ("b1c3", 8), ("c1g5", 7)]),
    # After 1.e4 e5 2.Nf3
    ("e2e4 e7e5 g1f3", [("b8c6", 40), ("g8f6", 45), ("f7f5", 5), ("d7d6", 10)]),
    # After 1.e4 c5 2.Nf3
    ("e2e4 c7c5 g1f3", [("d7d6", 25), ("b8c6", 30), ("e7e6", 20), ("g7g6", 15), ("d8b6", 10)]),
    # After 1.d4 d5 2.c4
    ("d2d4 d7d5 c2c4", [("e7e6", 35), ("c7c6", 25), ("d5c4", 15), ("g8f6", 25)]),
]


def _fen_key(state: GameState) -> tuple[str, str, str, str]:
    parts = state_to_fen(state).split()
    return (parts[0], parts[1], parts[2], parts[3])


def _apply_uci_line(start: GameState, uci_chain: str) -> GameState:
    s = start
    for token in uci_chain.split():
        if not token:
            continue
        mv = find_legal_move_matching(s, token[:4], token[4:5].upper() if len(token) > 4 else None)
        s = s.apply_move(mv)
    return s


def _build_table() -> _BookLine:
    out: _BookLine = {}
    start = GameState.initial()
    for prefix, replies in _RAW_BOOK:
        pos = _apply_uci_line(start, prefix)
        out[_fen_key(pos)] = replies
    return out


_BOOK = _build_table()


def lookup_book_move(state: GameState) -> Move | None:
    """Return a book move if the position is in the book, else None."""
    key = _fen_key(state)
    entries = _BOOK.get(key)
    if not entries:
        return None
    legal = get_legal_moves(state)
    legal_uci = {m.to_algebraic()[:4]: m for m in legal}
    weighted: list[tuple[Move, int]] = []
    for uci, w in entries:
        u4 = uci[:4].lower()
        if u4 not in legal_uci:
            continue
        mv = legal_uci[u4]
        if len(uci) > 4 and mv.promotion:
            try:
                mv = find_legal_move_matching(state, u4, uci[4:5].upper())
            except ValueError:
                continue
        weighted.append((mv, w))
    if not weighted:
        return None
    total = sum(w for _m, w in weighted)
    r = _rng.randint(1, total)
    acc = 0
    for mv, w in weighted:
        acc += w
        if r <= acc:
            return mv
    return weighted[-1][0]
