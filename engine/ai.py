from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Optional

from .evaluation import PIECE_VALUES, evaluate_position
from .opening_book import lookup_book_move
from .state import GameState, Move, get_game_status, get_legal_moves
from .zobrist import zobrist_hash

MATE_SCORE: Final[int] = 100_000
FLAG_EXACT: Final[int] = 0
FLAG_LOWER: Final[int] = 1
FLAG_UPPER: Final[int] = 2
_MAX_TT_ENTRIES: Final[int] = 350_000
_MAX_DEPTH: Final[int] = 32


def _clamp_search_depth(depth: int) -> int:
    return max(1, min(int(depth), _MAX_DEPTH))


def _move_key(m: Move) -> tuple[int, int, int, int, str | None, bool, bool]:
    return (
        m.start_row,
        m.start_col,
        m.end_row,
        m.end_col,
        m.promotion,
        m.is_en_passant,
        m.is_castle,
    )


def _move_from_key(k: tuple[int, int, int, int, str | None, bool, bool]) -> Move:
    return Move(
        k[0],
        k[1],
        k[2],
        k[3],
        promotion=k[4],
        is_en_passant=k[5],
        is_castle=k[6],
    )


def _same_move(a: Move, b: Move) -> bool:
    return _move_key(a) == _move_key(b)


@dataclass
class SearchInfo:
    best: Move | None
    multipv: list[tuple[Move, int]]
    nodes: int


class _SearchContext:
    __slots__ = ("tt", "nodes")

    def __init__(self) -> None:
        self.tt: dict[int, tuple[int, int, int, tuple[int, int, int, int, str | None, bool, bool] | None]] = {}
        self.nodes = 0

    def tt_store(
        self,
        key: int,
        depth: int,
        flag: int,
        score: int,
        best_move: Move | None,
    ) -> None:
        mk = _move_key(best_move) if best_move is not None else None
        old = self.tt.get(key)
        if old is not None and old[0] > depth:
            return
        if len(self.tt) >= _MAX_TT_ENTRIES and old is None:
            self.tt.pop(next(iter(self.tt)))
        self.tt[key] = (depth, flag, score, mk)


def _terminal_white_pov(state: GameState) -> int | None:
    status = get_game_status(state)
    if status == "ongoing":
        return None
    if status == "stalemate":
        return 0
    return -MATE_SCORE if state.white_to_move else MATE_SCORE


def _is_capture(state: GameState, move: Move) -> bool:
    if move.is_en_passant:
        return True
    return state.board[move.end_row][move.end_col] != "."


def _capture_moves(state: GameState) -> list[Move]:
    return [m for m in get_legal_moves(state) if _is_capture(state, m)]


def _mvv_lva_score(state: GameState, move: Move) -> int:
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


def _order_moves(state: GameState, moves: list[Move], tt_move: Move | None) -> list[Move]:
    out = list(moves)
    if tt_move is not None:
        for i, m in enumerate(out):
            if _same_move(m, tt_move):
                out.pop(i)
                out.insert(0, tt_move)
                break
    return sorted(out, key=lambda m: _mvv_lva_score(state, m), reverse=True)


def _tt_probe(
    ctx: _SearchContext,
    key: int,
    depth: int,
    alpha: int,
    beta: int,
) -> tuple[int, int, int | None, Move | None]:
    ent = ctx.tt.get(key)
    if ent is None:
        return alpha, beta, None, None
    d, flag, score, mk = ent
    tt_m = _move_from_key(mk) if mk else None
    if d < depth:
        return alpha, beta, None, tt_m
    if flag == FLAG_EXACT:
        return alpha, beta, score, tt_m
    if flag == FLAG_LOWER:
        alpha = max(alpha, score)
    else:
        beta = min(beta, score)
    if alpha >= beta:
        return alpha, beta, score, tt_m
    return alpha, beta, None, tt_m


def _quiescence(state: GameState, alpha: int, beta: int, ctx: _SearchContext, qdepth: int) -> int:
    ctx.nodes += 1
    stand = evaluate_position(state)

    if state.white_to_move:
        if stand >= beta:
            return beta
        best = stand
        alpha = max(alpha, best)
        if qdepth <= 0:
            return best
        caps = _capture_moves(state)
        for move in _order_moves(state, caps, None):
            s = _quiescence(state.apply_move(move), alpha, beta, ctx, qdepth - 1)
            if s > best:
                best = s
            if best >= beta:
                return best
            alpha = max(alpha, best)
        return best

    if stand <= alpha:
        return alpha
    best = stand
    beta = min(beta, best)
    if qdepth <= 0:
        return best
    caps = _capture_moves(state)
    for move in _order_moves(state, caps, None):
        s = _quiescence(state.apply_move(move), alpha, beta, ctx, qdepth - 1)
        if s < best:
            best = s
        if best <= alpha:
            return alpha
        beta = min(beta, best)
    return best


def _alphabeta(state: GameState, depth: int, alpha: int, beta: int, ctx: _SearchContext) -> int:
    ctx.nodes += 1

    term = _terminal_white_pov(state)
    if term is not None:
        return term

    key = zobrist_hash(state)
    alpha, beta, tcut, tt_best = _tt_probe(ctx, key, depth, alpha, beta)
    if tcut is not None:
        return tcut

    if depth == 0:
        return _quiescence(state, alpha, beta, ctx, qdepth=8)

    legal = get_legal_moves(state)
    if not legal:
        return _terminal_white_pov(state) or 0

    ordered = _order_moves(state, legal, tt_best)
    alpha_orig = alpha
    best_move: Move | None = None

    if state.white_to_move:
        best_score = -MATE_SCORE - 1
        for move in ordered:
            child = state.apply_move(move)
            score = _alphabeta(child, depth - 1, alpha, beta, ctx)
            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
        if best_score <= alpha_orig:
            flag = FLAG_UPPER
        elif best_score >= beta:
            flag = FLAG_LOWER
        else:
            flag = FLAG_EXACT
        ctx.tt_store(key, depth, flag, best_score, best_move)
        return best_score

    beta_orig = beta
    best_score = MATE_SCORE + 1
    for move in ordered:
        child = state.apply_move(move)
        score = _alphabeta(child, depth - 1, alpha, beta, ctx)
        if score < best_score:
            best_score = score
            best_move = move
        if score < beta:
            beta = score
        if beta <= alpha:
            break
    if best_score <= alpha:
        flag = FLAG_UPPER
    elif best_score >= beta_orig:
        flag = FLAG_LOWER
    else:
        flag = FLAG_EXACT
    ctx.tt_store(key, depth, flag, best_score, best_move)
    return best_score


def _search_root(state: GameState, depth: int, multipv: int, ctx: _SearchContext) -> SearchInfo:
    legal = get_legal_moves(state)
    if not legal:
        return SearchInfo(None, [], ctx.nodes)

    ordered = _order_moves(state, legal, None)
    scored: list[tuple[Move, int]] = []
    alpha = -MATE_SCORE
    beta = MATE_SCORE

    if state.white_to_move:
        for move in ordered:
            child = state.apply_move(move)
            s = _alphabeta(child, depth - 1, alpha, beta, ctx)
            scored.append((move, s))
            if s > alpha:
                alpha = s
    else:
        for move in ordered:
            child = state.apply_move(move)
            s = _alphabeta(child, depth - 1, alpha, beta, ctx)
            scored.append((move, s))
            if s < beta:
                beta = s

    scored.sort(
        key=lambda t: (t[1], _mvv_lva_score(state, t[0])),
        reverse=state.white_to_move,
    )
    uniq: list[tuple[Move, int]] = []
    seen: set[tuple[int, int, int, int, str | None, bool, bool]] = set()
    for mv, sc in scored:
        k = _move_key(mv)
        if k in seen:
            continue
        seen.add(k)
        uniq.append((mv, sc))
        if len(uniq) >= multipv:
            break

    best = uniq[0][0] if uniq else None
    return SearchInfo(best, uniq, ctx.nodes)


def pick_move_with_analysis(
    state: GameState, depth: int = 3, multipv: int = 3
) -> tuple[Optional[Move], SearchInfo]:
    """Opening book if available, else full search. Returns (move, analysis for UI)."""
    depth = _clamp_search_depth(depth)
    legal = get_legal_moves(state)
    if not legal:
        return None, SearchInfo(None, [], 0)
    book = lookup_book_move(state)
    if book is not None:
        return book, SearchInfo(book, [(book, 0)], 0)
    ctx = _SearchContext()
    info = _search_root(state, depth, max(1, multipv), ctx)
    return info.best, info


def choose_best_move(state: GameState, depth: int = 3) -> Optional[Move]:
    mv, _info = pick_move_with_analysis(state, depth, multipv=1)
    return mv


def analyze_root(state: GameState, depth: int = 3, multipv: int = 3) -> SearchInfo:
    """Full search with candidate root moves (for UI). Does not use the opening book."""
    depth = _clamp_search_depth(depth)
    ctx = _SearchContext()
    legal = get_legal_moves(state)
    if not legal:
        return SearchInfo(None, [], 0)
    return _search_root(state, depth, max(1, multipv), ctx)
