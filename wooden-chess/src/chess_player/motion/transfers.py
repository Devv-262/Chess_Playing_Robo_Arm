"""Chess move -> piece transfers (captures to the graveyard, castling, en passant, promotion via a spare), plus Slots and the error types.

The arm motion of one transfer is in simple_pick_place.py (the same code move.sh runs)."""
from dataclasses import dataclass

import chess
import numpy as np

from chess_player import config as C
from chess_player.geometry import square_center_mm
from chess_player.motion.ik import Unreachable


@dataclass
class Transfer:
    piece: str  # python-chess symbol, e.g. "P", "n"
    src: tuple  # board mm
    dst: tuple
    label: str  # for logs / commentary


class Blocked(Unreachable):
    """The swept gripper or the carried piece would hit another piece."""


class PieceDropped(RuntimeError):
    """The piece slipped out of the jaws while it was being carried."""


class GraspFailed(RuntimeError):
    pass


class MoveNotVerified(GraspFailed):
    """The arm finished but the camera does not show the board the move should have produced (and the automatic fix did not work).
    A GraspFailed, so main.py and the UI let the human finish the move by hand and then call push_robot_by_hand."""


class Slots:
    """Off-board places: one graveyard slot per captured piece, and the spare promotion pieces."""

    def __init__(self, board_to_robot=None):
        slots = list(C.GRAVEYARD)
        if board_to_robot is not None:  # nearest the robot base first: shortest, most reliable moves
            slots.sort(key=lambda xy: float(np.linalg.norm(board_to_robot(*xy)[:2])))
        self.free_graveyard = slots
        self.spares = {k: list(v) for k, v in C.SPARES.items()}
        self.occupied = {}  # graveyard xy -> piece symbol (obstacles for later moves)

    def graveyard(self, symbol="p"):
        if not self.free_graveyard:
            raise RuntimeError("graveyard full")
        xy = self.free_graveyard.pop(0)
        self.occupied[xy] = symbol
        return xy

    def spare(self, symbol):
        if not self.spares.get(symbol):
            raise RuntimeError(f"no spare {symbol} left for promotion: place one by hand")
        return self.spares[symbol].pop(0)


def _xy(sq):
    return tuple(square_center_mm(sq))


def surface_z(xy):
    """Height (board mm) of the surface a piece at xy stands on: the board, or the table beyond its outer edge."""
    x, y = xy
    lo, hi = -C.EDGE_MM, C.PLAY_MM + C.EDGE_MM
    return 0.0 if (lo <= x <= hi and lo <= y <= hi) else -C.BOARD_THICKNESS_MM


def plan_move(board: chess.Board, move: chess.Move, slots: Slots) -> list[Transfer]:
    """Transfers that turn the physical position `board` into board.push(move). `board` is not modified."""
    piece = board.piece_at(move.from_square)
    if piece is None:
        raise ValueError(f"no piece on {chess.square_name(move.from_square)}")
    out = []
    if board.is_castling(move):
        kingside = chess.square_file(move.to_square) > chess.square_file(move.from_square)
        rank = chess.square_rank(move.from_square)
        r_from, r_to = chess.square(7 if kingside else 0, rank), chess.square(5 if kingside else 3, rank)
        rook = board.piece_at(r_from).symbol()
        # Order so each piece is set down with the square on its h-file side (where the moving finger opens) empty:
        # kingside = rook to f1 first (g1 still empty), then king to g1 (h1 now empty); queenside = king to c1
        # first (d1 empty), then rook to d1 (e1 now empty).
        rook_t = Transfer(rook, _xy(r_from), _xy(r_to), f"rook {chess.square_name(r_from)}{chess.square_name(r_to)}")
        king_t = Transfer(piece.symbol(), _xy(move.from_square), _xy(move.to_square), f"king {move.uci()}")
        out += [rook_t, king_t] if kingside else [king_t, rook_t]
        return out

    if board.is_en_passant(move):
        cap_sq = chess.square(chess.square_file(move.to_square), chess.square_rank(move.from_square))
    elif board.is_capture(move):
        cap_sq = move.to_square
    else:
        cap_sq = None
    if cap_sq is not None:
        victim = board.piece_at(cap_sq).symbol()
        out.append(Transfer(victim, _xy(cap_sq), slots.graveyard(victim), f"capture {victim} on {chess.square_name(cap_sq)}"))

    if move.promotion:
        new = chess.Piece(move.promotion, piece.color).symbol()
        out.append(Transfer(piece.symbol(), _xy(move.from_square), slots.graveyard(piece.symbol()), "promoting pawn off the board"))
        out.append(Transfer(new, slots.spare(new), _xy(move.to_square), f"promote to {new} on {chess.square_name(move.to_square)}"))
    else:
        out.append(Transfer(piece.symbol(), _xy(move.from_square), _xy(move.to_square), f"{piece.symbol()} {move.uci()}"))
    return out


def obstacles_for(board: chess.Board, slots: Slots, transfers):
    """Yield (transfer, obstacles) with obstacles = {xy: symbol} of every other piece at that moment."""
    occ = {_xy(sq): p.symbol() for sq, p in board.piece_map().items()}
    occ.update(slots.occupied)
    for t in transfers:
        occ.pop(t.dst, None)  # a graveyard slot was pre-booked for this piece; it's empty until we put it there
        obst = {xy: s for xy, s in occ.items() if xy != t.src}
        yield t, obst
        occ.pop(t.src, None)
        occ[t.dst] = t.piece
