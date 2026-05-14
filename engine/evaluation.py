from __future__ import annotations

from typing import Final

from .state import GameState, is_in_check

PIECE_VALUES: Final[dict[str, int]] = {
    "p": 100,
    "n": 320,
    "b": 330,
    "r": 500,
    "q": 900,
    "k": 0,
}

# PeSTO piece values (centipawns) — see chessprogramming.org PeSTO's Evaluation Function
_MG_PIECE = (82, 337, 365, 477, 1025, 0)
_EG_PIECE = (94, 281, 297, 512, 936, 0)

_MG_PAWN = (
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    98,
    134,
    61,
    95,
    68,
    126,
    34,
    -11,
    -6,
    7,
    26,
    31,
    65,
    56,
    25,
    -20,
    -14,
    13,
    6,
    21,
    23,
    12,
    17,
    -23,
    -27,
    -2,
    -5,
    12,
    17,
    6,
    10,
    -25,
    -26,
    -4,
    -4,
    -10,
    3,
    3,
    33,
    -12,
    -35,
    -1,
    -20,
    -23,
    -15,
    24,
    38,
    -22,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
)

_EG_PAWN = (
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    178,
    173,
    158,
    134,
    147,
    132,
    165,
    187,
    94,
    100,
    85,
    67,
    56,
    53,
    82,
    84,
    32,
    24,
    13,
    5,
    -2,
    4,
    17,
    17,
    13,
    9,
    -3,
    -7,
    -7,
    -8,
    3,
    -1,
    4,
    7,
    -6,
    1,
    0,
    -5,
    -1,
    -8,
    13,
    8,
    8,
    10,
    13,
    0,
    2,
    -7,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
)

_MG_KNIGHT = (
    -167,
    -89,
    -34,
    -49,
    61,
    -97,
    -15,
    -107,
    -73,
    -41,
    72,
    36,
    23,
    62,
    7,
    -17,
    -47,
    60,
    37,
    65,
    84,
    129,
    73,
    44,
    -9,
    17,
    19,
    53,
    37,
    69,
    18,
    22,
    -13,
    4,
    16,
    13,
    28,
    19,
    21,
    -8,
    -23,
    -9,
    12,
    10,
    19,
    17,
    25,
    -16,
    -29,
    -53,
    -12,
    -3,
    -1,
    18,
    -14,
    -19,
    -105,
    -21,
    -58,
    -33,
    -17,
    -28,
    -19,
    -23,
)

_EG_KNIGHT = (
    -58,
    -38,
    -13,
    -28,
    -31,
    -27,
    -63,
    -99,
    -25,
    -8,
    -25,
    -2,
    -9,
    -25,
    -24,
    -52,
    -24,
    -20,
    10,
    9,
    -1,
    -9,
    -19,
    -41,
    -17,
    3,
    22,
    22,
    22,
    11,
    8,
    -18,
    -18,
    -6,
    16,
    25,
    16,
    17,
    4,
    -18,
    -23,
    -3,
    -1,
    15,
    10,
    -3,
    -20,
    -22,
    -42,
    -20,
    -10,
    -5,
    -2,
    -20,
    -23,
    -44,
    -29,
    -51,
    -23,
    -15,
    -22,
    -18,
    -50,
    -64,
)

_MG_BISHOP = (
    -29,
    4,
    -82,
    -37,
    -25,
    -42,
    7,
    -8,
    -26,
    16,
    -18,
    -13,
    30,
    59,
    18,
    -47,
    -16,
    37,
    43,
    40,
    35,
    50,
    37,
    -2,
    -4,
    5,
    19,
    50,
    37,
    37,
    7,
    -2,
    -6,
    13,
    13,
    26,
    34,
    12,
    10,
    4,
    0,
    15,
    15,
    15,
    14,
    27,
    18,
    10,
    4,
    15,
    16,
    0,
    7,
    21,
    33,
    1,
    -33,
    -3,
    -14,
    -21,
    -13,
    -12,
    -39,
    -21,
)

_EG_BISHOP = (
    -14,
    -21,
    -11,
    -8,
    -7,
    -9,
    -17,
    -24,
    -8,
    -4,
    7,
    -12,
    -3,
    -13,
    -4,
    -14,
    2,
    -8,
    0,
    -1,
    -2,
    6,
    0,
    4,
    -3,
    9,
    12,
    9,
    14,
    10,
    3,
    2,
    -6,
    3,
    13,
    19,
    7,
    10,
    -3,
    -9,
    -12,
    -3,
    8,
    10,
    13,
    3,
    -7,
    -15,
    -14,
    -18,
    -7,
    -1,
    4,
    -9,
    -15,
    -27,
    -23,
    -9,
    -23,
    -5,
    -9,
    -16,
    -5,
    -17,
)

_MG_ROOK = (
    32,
    42,
    32,
    51,
    63,
    9,
    31,
    43,
    27,
    32,
    58,
    62,
    80,
    67,
    26,
    44,
    -5,
    19,
    26,
    36,
    17,
    45,
    61,
    16,
    -24,
    -11,
    7,
    26,
    24,
    35,
    -8,
    -20,
    -36,
    -26,
    -12,
    -1,
    9,
    -7,
    6,
    -23,
    -45,
    -25,
    -16,
    -17,
    3,
    0,
    -5,
    -33,
    -44,
    -16,
    -20,
    -9,
    -1,
    11,
    -6,
    -71,
    -19,
    -13,
    1,
    17,
    16,
    7,
    -37,
    -26,
)

_EG_ROOK = (
    13,
    10,
    18,
    15,
    12,
    12,
    8,
    5,
    11,
    13,
    13,
    11,
    -3,
    3,
    8,
    3,
    7,
    7,
    7,
    5,
    4,
    -3,
    -5,
    -3,
    4,
    3,
    13,
    1,
    2,
    1,
    -1,
    2,
    3,
    5,
    8,
    4,
    -5,
    -6,
    -8,
    -11,
    -4,
    0,
    -5,
    -1,
    -7,
    -12,
    -8,
    -16,
    -6,
    -6,
    0,
    2,
    -9,
    -9,
    -11,
    -3,
    -9,
    2,
    3,
    -1,
    -5,
    -13,
    4,
    -20,
)

_MG_QUEEN = (
    -28,
    0,
    29,
    12,
    59,
    44,
    43,
    45,
    -24,
    -39,
    -5,
    1,
    -16,
    57,
    28,
    54,
    -13,
    -17,
    7,
    8,
    29,
    56,
    47,
    57,
    -27,
    -27,
    -16,
    -16,
    -1,
    17,
    -2,
    1,
    -9,
    -26,
    -9,
    -10,
    -2,
    -4,
    3,
    -3,
    -14,
    2,
    -11,
    -2,
    -5,
    2,
    14,
    5,
    -35,
    -8,
    11,
    2,
    8,
    15,
    -3,
    1,
    -1,
    -18,
    -9,
    10,
    -15,
    -25,
    -31,
    -50,
)

_EG_QUEEN = (
    -9,
    22,
    22,
    27,
    27,
    19,
    10,
    20,
    -17,
    20,
    32,
    41,
    58,
    25,
    30,
    0,
    -20,
    6,
    9,
    49,
    47,
    35,
    19,
    9,
    3,
    22,
    24,
    45,
    57,
    40,
    57,
    36,
    -18,
    28,
    19,
    47,
    31,
    34,
    39,
    23,
    -16,
    -27,
    15,
    6,
    9,
    17,
    10,
    5,
    -22,
    -23,
    -30,
    -16,
    -16,
    -23,
    -36,
    -32,
    -33,
    -28,
    -22,
    -43,
    -5,
    -32,
    -20,
    -41,
)

_MG_KING = (
    -65,
    23,
    16,
    -15,
    -56,
    -34,
    2,
    13,
    29,
    -1,
    -20,
    -7,
    -8,
    -4,
    -38,
    -29,
    -9,
    24,
    2,
    -16,
    -20,
    6,
    22,
    -22,
    -17,
    -20,
    -12,
    -27,
    -30,
    -25,
    -14,
    -36,
    -49,
    -1,
    -27,
    -39,
    -46,
    -44,
    -33,
    -51,
    -14,
    -14,
    -22,
    -46,
    -44,
    -30,
    -15,
    -27,
    1,
    7,
    -8,
    -64,
    -43,
    -16,
    9,
    8,
    -15,
    36,
    12,
    -54,
    8,
    -28,
    24,
    14,
)

_EG_KING = (
    -74,
    -35,
    -18,
    -18,
    -11,
    15,
    4,
    -17,
    -12,
    17,
    14,
    17,
    17,
    38,
    23,
    11,
    10,
    17,
    23,
    15,
    20,
    45,
    44,
    13,
    -8,
    22,
    24,
    27,
    26,
    33,
    26,
    3,
    -18,
    -4,
    21,
    24,
    27,
    23,
    9,
    -11,
    -19,
    -3,
    11,
    21,
    23,
    16,
    7,
    -9,
    -27,
    -11,
    4,
    13,
    14,
    4,
    -5,
    -17,
    -53,
    -34,
    -21,
    -11,
    -28,
    -14,
    -24,
    -43,
)

_MG_PSQ = (_MG_PAWN, _MG_KNIGHT, _MG_BISHOP, _MG_ROOK, _MG_QUEEN, _MG_KING)
_EG_PSQ = (_EG_PAWN, _EG_KNIGHT, _EG_BISHOP, _EG_ROOK, _EG_QUEEN, _EG_KING)

_PHASE_INC: Final[tuple[int, ...]] = (0, 1, 1, 2, 4, 0)  # pawn, N, B, R, Q, K


def _flip_sq(sq: int) -> int:
    return sq ^ 56


def _piece_type_index(piece: str) -> int:
    return "pnbrqk".index(piece.lower())


def _pawn_files_mask(state: GameState, white: bool) -> list[int]:
    counts = [0] * 8
    sym = "P" if white else "p"
    for row in range(8):
        for col in range(8):
            if state.board[row][col] == sym:
                counts[col] += 1
    return counts


def _is_passed_pawn(state: GameState, row: int, col: int, white: bool) -> bool:
    """True if no enemy pawn on this/adjacent files ahead of this pawn."""
    enemy = "p" if white else "P"
    if white:
        for r in range(0, row):
            for dc in (-1, 0, 1):
                c = col + dc
                if 0 <= c < 8 and state.board[r][c] == enemy:
                    return False
        return True
    for r in range(row + 1, 8):
        for dc in (-1, 0, 1):
            c = col + dc
            if 0 <= c < 8 and state.board[r][c] == enemy:
                return False
    return True


def _passed_and_structure(state: GameState) -> int:
    """Pawn structure / passed pawns from White's perspective (centipawns)."""
    w = 0
    w_files = _pawn_files_mask(state, True)
    b_files = _pawn_files_mask(state, False)
    for col, n in enumerate(w_files):
        if n > 1:
            w -= 15 * (n - 1)
    for col, n in enumerate(b_files):
        if n > 1:
            w += 15 * (n - 1)

    for row in range(8):
        for col in range(8):
            p = state.board[row][col]
            if p == "P" and _is_passed_pawn(state, row, col, True):
                rank_from_home = 6 - row
                w += 20 + rank_from_home * 18
            elif p == "p" and _is_passed_pawn(state, row, col, False):
                rank_from_home = row - 1
                w -= 20 + rank_from_home * 18
    return w


def _king_shield_and_tropism(state: GameState) -> int:
    """Crude king safety from White's perspective (positive favors White)."""
    bonus = 0

    def king_sq(sym: str) -> tuple[int, int] | None:
        for r in range(8):
            for c in range(8):
                if state.board[r][c] == sym:
                    return r, c
        return None

    wk = king_sq("K")
    bk = king_sq("k")
    if wk is None or bk is None:
        return 0

    wr, wc = wk
    # White king: shield pawns on ranks closer to black (smaller row index = higher board)
    for dr in (1, 2):
        for dc in (-1, 0, 1):
            r, c = wr - dr, wc + dc
            if 0 <= r < 8 and 0 <= c < 8 and state.board[r][c] == "P":
                bonus += 6

    br, bc = bk
    for dr in (1, 2):
        for dc in (-1, 0, 1):
            r, c = br + dr, bc + dc
            if 0 <= r < 8 and 0 <= c < 8 and state.board[r][c] == "p":
                bonus -= 6

    # Tropism: enemy pieces near our king (Manhattan), scaled lightly
    for r in range(8):
        for c in range(8):
            p = state.board[r][c]
            if p == "." or p.lower() == "k":
                continue
            dist_w = abs(r - wr) + abs(c - wc)
            dist_b = abs(r - br) + abs(c - bc)
            if p.islower():  # black piece — pressure on white king
                if p == "q":
                    bonus -= max(0, 14 - dist_w) * 3
                elif p in ("r", "n", "b"):
                    bonus -= max(0, 10 - dist_w) * 1
            else:  # white piece — pressure on black king
                if p == "Q":
                    bonus += max(0, 14 - dist_b) * 3
                elif p in ("R", "N", "B"):
                    bonus += max(0, 10 - dist_b) * 1

    # Open file next to king (no friendly pawn on file) — small penalty
    for side_col in (wc - 1, wc + 1):
        if 0 <= side_col < 8:
            file_open = True
            for rr in range(8):
                if state.board[rr][side_col] == "P":
                    file_open = False
                    break
            if file_open:
                bonus -= 8
    for side_col in (bc - 1, bc + 1):
        if 0 <= side_col < 8:
            file_open = True
            for rr in range(8):
                if state.board[rr][side_col] == "p":
                    file_open = False
                    break
            if file_open:
                bonus += 8

    if is_in_check(state, True):
        bonus -= 35
    if is_in_check(state, False):
        bonus += 35

    return bonus


def evaluate_position(state: GameState) -> int:
    """Static evaluation in centipawns from White's perspective."""
    mg_w = mg_b = eg_w = eg_b = 0
    phase = 0
    board = state.board

    for row in range(8):
        for col in range(8):
            p = board[row][col]
            if p == ".":
                continue
            sq = row * 8 + col
            pt = _piece_type_index(p)
            inc = _PHASE_INC[pt]
            if p.isupper():
                phase += inc
                mg_w += _MG_PIECE[pt] + _MG_PSQ[pt][sq]
                eg_w += _EG_PIECE[pt] + _EG_PSQ[pt][sq]
            else:
                phase += inc
                fsq = _flip_sq(sq)
                mg_b += _MG_PIECE[pt] + _MG_PSQ[pt][fsq]
                eg_b += _EG_PIECE[pt] + _EG_PSQ[pt][fsq]

    phase = min(phase, 24)
    mg_score = mg_w - mg_b
    eg_score = eg_w - eg_b
    tapered = (mg_score * phase + eg_score * (24 - phase)) // 24

    tapered += _passed_and_structure(state)
    tapered += _king_shield_and_tropism(state)
    return int(tapered)
