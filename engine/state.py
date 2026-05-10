from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


PROMOTIONS = ("Q", "R", "B", "N")


@dataclass(frozen=True)
class CastlingRights:
    wk: bool = True
    wq: bool = True
    bk: bool = True
    bq: bool = True


@dataclass(frozen=True)
class Move:
    start_row: int
    start_col: int
    end_row: int
    end_col: int
    promotion: Optional[str] = None
    is_en_passant: bool = False
    is_castle: bool = False

    def to_algebraic(self) -> str:
        start = f"{chr(self.start_col + ord('a'))}{8 - self.start_row}"
        end = f"{chr(self.end_col + ord('a'))}{8 - self.end_row}"
        promotion = f"={self.promotion}" if self.promotion else ""
        return f"{start}{end}{promotion}"


@dataclass
class GameState:
    board: list[list[str]]
    white_to_move: bool = True
    castling_rights: CastlingRights = field(default_factory=CastlingRights)
    en_passant_target: Optional[tuple[int, int]] = None
    halfmove_clock: int = 0
    fullmove_number: int = 1

    @classmethod
    def initial(cls) -> "GameState":
        return cls(
            board=[
                list("rnbqkbnr"),
                list("pppppppp"),
                list("........"),
                list("........"),
                list("........"),
                list("........"),
                list("PPPPPPPP"),
                list("RNBQKBNR"),
            ]
        )

    def piece_at(self, row: int, col: int) -> str:
        return self.board[row][col]

    def apply_move(self, move: Move) -> "GameState":
        board_copy = [row[:] for row in self.board]
        piece = board_copy[move.start_row][move.start_col]
        target_piece = board_copy[move.end_row][move.end_col]

        board_copy[move.start_row][move.start_col] = "."

        if move.is_en_passant:
            capture_row = move.end_row + 1 if piece.isupper() else move.end_row - 1
            target_piece = board_copy[capture_row][move.end_col]
            board_copy[capture_row][move.end_col] = "."

        if move.is_castle:
            if move.end_col == 6:
                rook_start_col, rook_end_col = 7, 5
            else:
                rook_start_col, rook_end_col = 0, 3

            board_copy[move.end_row][rook_end_col] = board_copy[move.end_row][rook_start_col]
            board_copy[move.end_row][rook_start_col] = "."

        if move.promotion and piece.lower() == "p":
            promoted_piece = move.promotion if piece.isupper() else move.promotion.lower()
            board_copy[move.end_row][move.end_col] = promoted_piece
        else:
            board_copy[move.end_row][move.end_col] = piece

        rights = self.castling_rights
        wk, wq, bk, bq = rights.wk, rights.wq, rights.bk, rights.bq

        if piece == "K":
            wk = False
            wq = False
        elif piece == "k":
            bk = False
            bq = False
        elif piece == "R":
            if move.start_row == 7 and move.start_col == 0:
                wq = False
            elif move.start_row == 7 and move.start_col == 7:
                wk = False
        elif piece == "r":
            if move.start_row == 0 and move.start_col == 0:
                bq = False
            elif move.start_row == 0 and move.start_col == 7:
                bk = False

        if target_piece == "R":
            if move.end_row == 7 and move.end_col == 0:
                wq = False
            elif move.end_row == 7 and move.end_col == 7:
                wk = False
        elif target_piece == "r":
            if move.end_row == 0 and move.end_col == 0:
                bq = False
            elif move.end_row == 0 and move.end_col == 7:
                bk = False

        new_en_passant_target: Optional[tuple[int, int]] = None
        if piece.lower() == "p" and abs(move.end_row - move.start_row) == 2:
            mid_row = (move.end_row + move.start_row) // 2
            new_en_passant_target = (mid_row, move.start_col)

        is_pawn_move = piece.lower() == "p"
        is_capture = target_piece != "."

        next_halfmove_clock = 0 if (is_pawn_move or is_capture) else self.halfmove_clock + 1
        next_fullmove_number = self.fullmove_number + (0 if self.white_to_move else 1)

        return GameState(
            board=board_copy,
            white_to_move=not self.white_to_move,
            castling_rights=CastlingRights(wk=wk, wq=wq, bk=bk, bq=bq),
            en_passant_target=new_en_passant_target,
            halfmove_clock=next_halfmove_clock,
            fullmove_number=next_fullmove_number,
        )


def get_legal_moves(state: GameState) -> list[Move]:
    pseudo_moves = _generate_pseudo_legal_moves(state)
    moving_side_is_white = state.white_to_move
    legal_moves: list[Move] = []

    for move in pseudo_moves:
        next_state = state.apply_move(move)
        if not is_in_check(next_state, moving_side_is_white):
            legal_moves.append(move)

    return legal_moves


def get_game_status(state: GameState) -> str:
    legal_moves = get_legal_moves(state)
    if legal_moves:
        return "ongoing"
    if is_in_check(state, state.white_to_move):
        return "checkmate"
    return "stalemate"


def is_in_check(state: GameState, is_white: bool) -> bool:
    king_symbol = "K" if is_white else "k"
    king_pos = _find_piece(state.board, king_symbol)
    if king_pos is None:
        return True
    return is_square_attacked(state, king_pos[0], king_pos[1], by_white=not is_white)


def is_square_attacked(state: GameState, row: int, col: int, by_white: bool) -> bool:
    board = state.board

    pawn_attack_row = row + 1 if by_white else row - 1
    pawn_symbol = "P" if by_white else "p"
    for dc in (-1, 1):
        pawn_col = col + dc
        if _in_bounds(pawn_attack_row, pawn_col) and board[pawn_attack_row][pawn_col] == pawn_symbol:
            return True

    knight_symbol = "N" if by_white else "n"
    for dr, dc in (
        (-2, -1),
        (-2, 1),
        (-1, -2),
        (-1, 2),
        (1, -2),
        (1, 2),
        (2, -1),
        (2, 1),
    ):
        r, c = row + dr, col + dc
        if _in_bounds(r, c) and board[r][c] == knight_symbol:
            return True

    bishop_symbol = "B" if by_white else "b"
    rook_symbol = "R" if by_white else "r"
    queen_symbol = "Q" if by_white else "q"
    king_symbol = "K" if by_white else "k"

    for dr, dc in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
        r, c = row + dr, col + dc
        while _in_bounds(r, c):
            piece = board[r][c]
            if piece != ".":
                if piece in (bishop_symbol, queen_symbol):
                    return True
                break
            r += dr
            c += dc

    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        r, c = row + dr, col + dc
        while _in_bounds(r, c):
            piece = board[r][c]
            if piece != ".":
                if piece in (rook_symbol, queen_symbol):
                    return True
                break
            r += dr
            c += dc

    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            r, c = row + dr, col + dc
            if _in_bounds(r, c) and board[r][c] == king_symbol:
                return True

    return False


def _generate_pseudo_legal_moves(state: GameState) -> list[Move]:
    moves: list[Move] = []

    for row in range(8):
        for col in range(8):
            piece = state.board[row][col]
            if piece == ".":
                continue
            if piece.isupper() != state.white_to_move:
                continue

            piece_type = piece.lower()
            if piece_type == "p":
                _add_pawn_moves(state, row, col, moves)
            elif piece_type == "n":
                _add_knight_moves(state, row, col, moves)
            elif piece_type == "b":
                _add_sliding_moves(state, row, col, moves, [(-1, -1), (-1, 1), (1, -1), (1, 1)])
            elif piece_type == "r":
                _add_sliding_moves(state, row, col, moves, [(-1, 0), (1, 0), (0, -1), (0, 1)])
            elif piece_type == "q":
                _add_sliding_moves(
                    state,
                    row,
                    col,
                    moves,
                    [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)],
                )
            elif piece_type == "k":
                _add_king_moves(state, row, col, moves)

    return moves


def _add_pawn_moves(state: GameState, row: int, col: int, moves: list[Move]) -> None:
    board = state.board
    piece = board[row][col]
    is_white = piece.isupper()
    direction = -1 if is_white else 1
    start_row = 6 if is_white else 1
    promotion_row = 0 if is_white else 7

    one_forward = row + direction
    if _in_bounds(one_forward, col) and board[one_forward][col] == ".":
        if one_forward == promotion_row:
            for promotion_piece in PROMOTIONS:
                moves.append(Move(row, col, one_forward, col, promotion=promotion_piece))
        else:
            moves.append(Move(row, col, one_forward, col))

        two_forward = row + 2 * direction
        if row == start_row and board[two_forward][col] == ".":
            moves.append(Move(row, col, two_forward, col))

    for dc in (-1, 1):
        target_col = col + dc
        target_row = row + direction
        if not _in_bounds(target_row, target_col):
            continue

        target_piece = board[target_row][target_col]
        if target_piece != "." and target_piece.isupper() != is_white:
            if target_row == promotion_row:
                for promotion_piece in PROMOTIONS:
                    moves.append(Move(row, col, target_row, target_col, promotion=promotion_piece))
            else:
                moves.append(Move(row, col, target_row, target_col))

        if state.en_passant_target == (target_row, target_col):
            moves.append(Move(row, col, target_row, target_col, is_en_passant=True))


def _add_knight_moves(state: GameState, row: int, col: int, moves: list[Move]) -> None:
    board = state.board
    is_white = board[row][col].isupper()
    offsets = (
        (-2, -1),
        (-2, 1),
        (-1, -2),
        (-1, 2),
        (1, -2),
        (1, 2),
        (2, -1),
        (2, 1),
    )
    for dr, dc in offsets:
        r, c = row + dr, col + dc
        if not _in_bounds(r, c):
            continue
        target = board[r][c]
        if target == "." or target.isupper() != is_white:
            moves.append(Move(row, col, r, c))


def _add_sliding_moves(
    state: GameState,
    row: int,
    col: int,
    moves: list[Move],
    directions: list[tuple[int, int]],
) -> None:
    board = state.board
    is_white = board[row][col].isupper()
    for dr, dc in directions:
        r, c = row + dr, col + dc
        while _in_bounds(r, c):
            target = board[r][c]
            if target == ".":
                moves.append(Move(row, col, r, c))
            else:
                if target.isupper() != is_white:
                    moves.append(Move(row, col, r, c))
                break
            r += dr
            c += dc


def _add_king_moves(state: GameState, row: int, col: int, moves: list[Move]) -> None:
    board = state.board
    piece = board[row][col]
    is_white = piece.isupper()

    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            r, c = row + dr, col + dc
            if not _in_bounds(r, c):
                continue
            target = board[r][c]
            if target == "." or target.isupper() != is_white:
                moves.append(Move(row, col, r, c))

    rights = state.castling_rights
    if is_white and row == 7 and col == 4:
        if rights.wk and board[7][7] == "R" and board[7][5] == "." and board[7][6] == ".":
            if not is_square_attacked(state, 7, 4, by_white=False) and not is_square_attacked(
                state, 7, 5, by_white=False
            ) and not is_square_attacked(state, 7, 6, by_white=False):
                moves.append(Move(7, 4, 7, 6, is_castle=True))

        if rights.wq and board[7][0] == "R" and board[7][1] == "." and board[7][2] == "." and board[7][3] == ".":
            if not is_square_attacked(state, 7, 4, by_white=False) and not is_square_attacked(
                state, 7, 3, by_white=False
            ) and not is_square_attacked(state, 7, 2, by_white=False):
                moves.append(Move(7, 4, 7, 2, is_castle=True))

    if not is_white and row == 0 and col == 4:
        if rights.bk and board[0][7] == "r" and board[0][5] == "." and board[0][6] == ".":
            if not is_square_attacked(state, 0, 4, by_white=True) and not is_square_attacked(
                state, 0, 5, by_white=True
            ) and not is_square_attacked(state, 0, 6, by_white=True):
                moves.append(Move(0, 4, 0, 6, is_castle=True))

        if rights.bq and board[0][0] == "r" and board[0][1] == "." and board[0][2] == "." and board[0][3] == ".":
            if not is_square_attacked(state, 0, 4, by_white=True) and not is_square_attacked(
                state, 0, 3, by_white=True
            ) and not is_square_attacked(state, 0, 2, by_white=True):
                moves.append(Move(0, 4, 0, 2, is_castle=True))


def _find_piece(board: list[list[str]], target_piece: str) -> Optional[tuple[int, int]]:
    for row in range(8):
        for col in range(8):
            if board[row][col] == target_piece:
                return row, col
    return None


def _in_bounds(row: int, col: int) -> bool:
    return 0 <= row < 8 and 0 <= col < 8
