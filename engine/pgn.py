from __future__ import annotations

import re
from typing import Optional

from datetime import date

from .state import GameState, Move, get_legal_moves


def build_pgn(
    moves: list[Move],
    *,
    result: str,
    white_name: str = "Human",
    black_name: str = "Engine",
    event: str = "Casual Game",
    site: str = "?",
    time_control: str | None = None,
) -> str:
    today = date.today().isoformat()
    headers = [
        f'[Event "{event}"]',
        f'[Site "{site}"]',
        f'[Date "{today}"]',
        f'[White "{white_name}"]',
        f'[Black "{black_name}"]',
    ]
    if time_control:
        headers.append(f'[TimeControl "{time_control}"]')
    headers.append(f'[Result "{result}"]')
    header_block = "\n".join(headers)
    body = _movetext(moves)
    if body:
        return header_block + "\n\n" + body + " " + result + "\n"
    return header_block + "\n\n" + result + "\n"


def _movetext(moves: list[Move]) -> str:
    if not moves:
        return ""
    chunks: list[str] = []
    for index in range(0, len(moves), 2):
        turn_no = (index // 2) + 1
        white_san = moves[index].to_algebraic()
        line = f"{turn_no}. {white_san}"
        if index + 1 < len(moves):
            line += f" {moves[index + 1].to_algebraic()}"
        chunks.append(line)
    return " ".join(chunks)


_COORD_TOKEN = re.compile(
    r"\b([a-h][1-8][a-h][1-8])(?:=?([QRBNqrbn]))?\b",
)


def strip_pgn_noise(text: str) -> str:
    s = re.sub(r"\{[^}]*\}", " ", text)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r";[^\n]*", " ", s)
    s = re.sub(r"%[^\n]*", " ", s)
    return s


def extract_coordinate_moves(text: str) -> list[tuple[str, Optional[str]]]:
    cleaned = strip_pgn_noise(text)
    out: list[tuple[str, Optional[str]]] = []
    for m in _COORD_TOKEN.finditer(cleaned):
        uci = m.group(1).lower()
        prom = m.group(2)
        if prom is not None:
            prom = prom.upper()
        out.append((uci, prom))
    return out


def uci_to_squares(uci: str) -> tuple[int, int, int, int]:
    if len(uci) != 4:
        raise ValueError("UCI move must be 4 characters")
    sc = ord(uci[0]) - ord("a")
    sr = 8 - int(uci[1])
    ec = ord(uci[2]) - ord("a")
    er = 8 - int(uci[3])
    if not (0 <= sc < 8 and 0 <= sr < 8 and 0 <= ec < 8 and 0 <= er < 8):
        raise ValueError("UCI move is off the board")
    return sr, sc, er, ec


def find_legal_move_matching(
    state: GameState,
    uci: str,
    promotion: Optional[str],
) -> Move:
    sr, sc, er, ec = uci_to_squares(uci)
    legal = get_legal_moves(state)
    candidates = [
        mv
        for mv in legal
        if mv.start_row == sr
        and mv.start_col == sc
        and mv.end_row == er
        and mv.end_col == ec
    ]
    if not candidates:
        raise ValueError(f"No legal move matches {uci} in this position")
    if len(candidates) == 1:
        return candidates[0]
    if promotion:
        prom_u = promotion.upper()
        for mv in candidates:
            if mv.promotion == prom_u:
                return mv
        raise ValueError(f"Promotion {promotion} not legal for {uci}")
    for mv in candidates:
        if mv.promotion == "Q":
            return mv
    return candidates[0]


def replay_coordinate_moves(
    moves: list[tuple[str, Optional[str]]],
    *,
    start: GameState | None = None,
) -> tuple[GameState, list[GameState], list[Move]]:
    state = GameState.initial() if start is None else start
    states: list[GameState] = [state]
    applied: list[Move] = []
    for uci, prom in moves:
        mv = find_legal_move_matching(state, uci, prom)
        state = state.apply_move(mv)
        states.append(state)
        applied.append(mv)
    return state, states, applied
