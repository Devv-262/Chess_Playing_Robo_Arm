"""The ONE pick-and-place (what scripts/move.sh runs, and what the game plays): no camera, no board map, no sag settle, no shift search.

One transfer = one piece carried from a source point to a target point:
  1. jaws open to the piece's open_pct, the arm goes (at the carry height) to the taught centre of the source square + the piece's fixed-finger offset
  2. straight down to z = grip_tip, close fully (1 %): below EMPTY_PCT = nothing in the hand -> open and retry (TRIES), else hold at width - squeeze
  3. straight up, across at the carry height, straight down to the place height, open to contact + release_pct, straight up
Centres come from data/center_teach.json (written by scripts/anchor.sh: one hand-taught square, the rest +30 mm steps). Off-board points (graveyard, spare
queens) use the offset of the nearest board square. Per-piece numbers: data/wooden_grasps.json (recipe()).
"""
import json
import time

import chess
import numpy as np

from chess_player import config as C
from chess_player.geometry import BoardToRobot, board_from_robot, mm_to_square, square_center_mm
from chess_player.motion.arm import Arm, FakeArm, look_pose
from chess_player.motion.ik import IK, Unreachable
from chess_player.motion.transfers import GraspFailed, PieceDropped, Transfer, obstacles_for, plan_move, surface_z

SIDE_SPEED = 40.0  # mm/s sideways at carry height
UP_SPEED = 30.0
CLOSE_S = 1.0
OPEN_S = 1.0
EMPTY_PCT = C.GRIPPER_MIN_PCT + 2.0  # jaws closed to less than this = nothing in the hand
TRIES = 3
CARRY_MM = 100.0  # carry height above the grip height (piece bottom >= 70 mm above the board + 30 mm extra); lowered where the arm cannot reach
# Tuned by the user on the real arm: the put-down 8 mm higher. (The old -5 mm X shift of every centre was removed 2026-11-13.)
PLACE_DZ = 8.0
TEMP_CENTRE_DX_MM = 9.0  # TEMPORARY test (user 2026-11-13): every centre 9 mm toward +X (robot right, h-file) and 2 mm toward +Y (forward, rank 8). NOT confirmed: set both to 0.0 or delete unless the user says keep it
TEMP_CENTRE_DY_MM = 2.0
FILE = C.DATA / "wooden_grasps.json"
CENTRES = C.DATA / "center_teach.json"
PAWN = dict(open_pct=16.1, shift_x=-10.6, shift_y=2.7, grip_tip=15.0, place_dx=3.0, place_dy=0.0, place_extra=2.0,
            contact_pct=8.3, squeeze=C.HOLD_SQUEEZE_PCT, vert_speed=25.0, release_pct=4.0)


def recipe(piece):
    """Numbers for one piece type (pawn defaults, then data/wooden_grasps.json)."""
    piece = piece.lower()
    d = dict(PAWN)
    try:
        saved = json.loads(FILE.read_text()).get(piece)
    except (OSError, ValueError):
        saved = None
    if saved:
        saved = dict(saved)
        saved.pop("complete", None)
        d.update(saved)
    return d


def _centres():
    try:
        return json.loads(CENTRES.read_text())
    except (OSError, ValueError):
        raise Unreachable("no centres: run scripts/anchor.sh")


def taught_xy(square, T=None, centres=None):
    """Board mm of the taught centre of `square`: the arm's real tip position (robot frame) of the data file, turned into board mm with the CURRENT calibration."""
    d = centres or _centres()
    if square not in d:
        raise Unreachable(f"the centre of {square} is not in data/center_teach.json: run scripts/anchor.sh")
    xy = board_from_robot(T or BoardToRobot.load(), np.array(d[square]["tip_robot_mm"], float) / 1000.0)[:2]
    return np.array(xy, float) + np.array([TEMP_CENTRE_DX_MM, TEMP_CENTRE_DY_MM])


def point_xy(xy, T=None, centres=None):
    """Board mm of the TAUGHT version of a point: a square centre -> its taught centre; off the board -> the point plus the offset of the nearest square."""
    sq = mm_to_square(*xy)
    if sq is not None:
        return taught_xy(chess.square_name(sq), T, centres)
    x = min(max(float(xy[0]), 0.0), C.PLAY_MM)
    y = min(max(float(xy[1]), 0.0), C.PLAY_MM)
    near = chess.square_name(mm_to_square(min(x, C.PLAY_MM - 1e-3), min(y, C.PLAY_MM - 1e-3)))
    off = taught_xy(near, T, centres) - np.array(square_center_mm(chess.parse_square(near)), float)
    return np.array(xy, float) + off


class SimplePickPlace:
    """Drop-in for the game (Session / UI): play, check, execute, go_look."""

    def __init__(self, arm, ik, T, verify_grasp=True, log=print):
        self.arm, self.ik, self.T, self.log = arm, ik, T, log

    # ------------------------------------------------------------ planning
    def _plan(self, t: Transfer):
        r = recipe(t.piece)
        T, ik = self.T, self.ik
        gap = float(np.interp(r["contact_pct"], C._GAP_PCT, C._GAP_MM))
        cen = _centres()
        p_src = point_xy(t.src, T, cen) + np.array([r["shift_x"], r["shift_y"]])
        p_dst = point_xy(t.dst, T, cen) + np.array([-gap / 2.0 + r["place_dx"], r["shift_y"] + r["place_dy"]])
        z_pick = surface_z(t.src) + r["grip_tip"]
        z_place = surface_z(t.dst) + r["grip_tip"] + r["place_extra"] + PLACE_DZ
        open_pct = min(r["open_pct"], C.GRIP_OPEN_MAX_PCT)
        close_pct = max(0.0, r["contact_pct"] - r["squeeze"])
        release_pct = min(open_pct, r["contact_pct"] + r["release_pct"])
        look = {**look_pose(), "gripper": open_pct}
        seed = np.array([look[j] for j in C.ARM_JOINTS], float)
        seed[4] = C.WRIST_ROLL_DEG

        def ik_at(xy, z, sd):
            q, err, tilt = ik.solve(T(xy[0], xy[1], z), sd, C.GRASP_MAX_TILT)
            if err > C.IK_MAX_ERR_MM or tilt > C.GRASP_MAX_TILT:
                raise Unreachable(f"{t.label}: IK error {err:.1f} mm, tilt {tilt:.0f} deg at ({xy[0]:.0f}, {xy[1]:.0f}, {z:.0f})")
            return q

        z_carry = max(r["grip_tip"], 0.0) + CARRY_MM
        while z_carry > max(z_pick, z_place) + 10:
            try:
                for xy in (p_src, p_dst, (p_src + p_dst) / 2):
                    ik_at(xy, z_carry, seed)
                break
            except Unreachable:
                z_carry -= 5.0
        else:
            raise Unreachable(f"{t.label}: the arm cannot carry above the grip height between these points")

        def leg(sd, xy0, z0, xy1, z1, speed, grip):
            L = float(np.linalg.norm(np.r_[xy1 - xy0, z1 - z0]))
            n = max(1, int(np.ceil(L / 6.0)))
            wps = []
            for i in range(1, n + 1):
                f = i / n
                sd = ik_at(xy0 + (xy1 - xy0) * f, z0 + (z1 - z0) * f, sd)
                wps.append({**dict(zip(C.ARM_JOINTS, sd)), "gripper": grip})
            return wps, max(0.6, L / speed), sd

        first_q = ik_at(p_src, z_carry, seed)
        sd, legs = first_q, []
        for name, a0, za, b0, zb, sp, g in (
            ("down", p_src, z_carry, p_src, z_pick, r["vert_speed"], open_pct),
            ("lift", p_src, z_pick, p_src, z_carry, r["vert_speed"], close_pct),
            ("carry", p_src, z_carry, p_dst, z_carry, SIDE_SPEED, close_pct),
            ("lower", p_dst, z_carry, p_dst, z_place, r["vert_speed"], close_pct),
            ("up", p_dst, z_place, p_dst, z_carry, UP_SPEED, release_pct),
        ):
            w, dur, sd = leg(sd, a0, za, b0, zb, sp, g)
            legs.append((name, w, dur))
        info = dict(step=t.label, src=p_src.round(1).tolist(), dst=p_dst.round(1).tolist(), z_pick=round(z_pick, 1), z_place=round(z_place, 1),
                    z_carry=round(z_carry, 1))
        return dict(r=r, legs=legs, first_q=first_q, open_pct=open_pct, close_pct=close_pct, release_pct=release_pct, look=look, info=info)

    def plan_transfer(self, t: Transfer, obstacles=None):
        return {"info": self._plan(t)["info"]}

    def check(self, board, move, slots):
        import copy

        if move not in board.legal_moves:
            return dict(valid=False, reason=f"{move.uci()} is not legal here")
        sl = copy.deepcopy(slots)
        steps, ok_all = [], True
        try:
            transfers = list(obstacles_for(board, sl, plan_move(board, move, sl)))
        except RuntimeError as e:  # no spare piece for an under-promotion, graveyard full
            return dict(valid=True, uci=move.uci(), san=board.san(move), physical_ok=False,
                        steps=[dict(ok=False, step=move.uci(), problem="NoSlot", details=str(e))])
        for t, obst in transfers:
            try:
                steps.append(dict(ok=True, **self.plan_transfer(t, obst)["info"]))
            except Unreachable as e:
                ok_all = False
                steps.append(dict(ok=False, step=t.label, problem=type(e).__name__, details=str(e)))
        return dict(valid=True, uci=move.uci(), san=board.san(move), physical_ok=ok_all, steps=steps)

    # ------------------------------------------------------------ execution
    def go_look(self):
        self.arm.move_to({**look_pose(), "gripper": C.GRIPPER_LOOK}, 2.0)

    def execute(self, t: Transfer, retries=None, obstacles=None, home=False):
        """Carry one piece. Raises GraspFailed if nothing is gripped after TRIES (the arm goes up first)."""
        p = self._plan(t)
        arm, r, legs = self.arm, p["r"], p["legs"]
        self.log(f"  {t.label}: pick {p['info']['src']} -> place {p['info']['dst']} | z pick {p['info']['z_pick']}, place {p['info']['z_place']}, carry {p['info']['z_carry']}")
        if isinstance(arm, FakeArm):
            return True
        try:
            if home:
                arm.move_to(p["look"], 4.0)
            arm.move_to({**dict(zip(C.ARM_JOINTS, p["first_q"])), "gripper": p["open_pct"]}, 3.0)
            arm.move_path([arm.joints()] + legs[0][1], legs[0][2])
            time.sleep(0.5)
            held = False
            for attempt in range(TRIES):
                arm.gripper(C.GRIPPER_MIN_PCT, CLOSE_S)
                time.sleep(0.6)
                g = float(arm.present()["gripper"])
                if g >= EMPTY_PCT:
                    held = True
                    arm.gripper(max(0.0, g - r["squeeze"]), 0.3)
                    time.sleep(0.4)
                    self.log(f"    gripped at {g:.1f} % (attempt {attempt + 1})")
                    break
                self.log(f"    attempt {attempt + 1}: the jaws closed to {g:.1f} %, nothing in the hand")
                arm.gripper(p["open_pct"], OPEN_S)
                time.sleep(0.6)
            if not held:
                arm.move_path([arm.joints()] + [{**w, "gripper": p["open_pct"]} for w in legs[1][1]], legs[1][2])
                raise GraspFailed(f"{t.label}: nothing gripped after {TRIES} tries")
            for name, w, dur in legs[1:4]:
                arm.move_path([arm.joints()] + w, dur)
            time.sleep(0.3)
            arm.gripper(p["release_pct"], OPEN_S)
            time.sleep(0.5)
            arm.move_path([arm.joints()] + legs[4][1], legs[4][2])
            if home:
                arm.move_to(p["look"], 4.0)
        except KeyboardInterrupt:
            self.log("stopped, freezing the arm")
            arm.freeze()
            raise
        return True

    def play(self, board, move, slots, recover=None):
        """Play `move` (all its transfers). recover(transfer, error) -> "done" | new source xy (board mm) | None (give up)."""
        try:
            transfers = list(obstacles_for(board, slots, plan_move(board, move, slots)))
        except RuntimeError as e:
            raise Unreachable(str(e))
        for t, _ in transfers:  # fail before moving if anything is unreachable
            self._plan(t)
        for t, obst in transfers:
            for attempt in range(C.RECOVERY_ATTEMPTS + 1):
                try:
                    self.execute(t, obstacles=obst)
                    break
                except (GraspFailed, PieceDropped) as e:
                    if recover is None or attempt == C.RECOVERY_ATTEMPTS:
                        self.go_look()
                        raise
                    where = recover(t, e)
                    if where == "done":
                        break
                    if where is None:
                        self.go_look()
                        raise
                    t = Transfer(t.piece, tuple(where), t.dst, t.label + " (retry)")
        self.go_look()
        return [t for t, _ in transfers]


def run(piece, src, dst, arm=None, log=print, home=True):
    """move.sh: one piece from the square `src` to the square `dst`. Returns True if it was gripped and placed."""
    own = arm is None
    arm = arm or Arm(use_sag_model=False)
    pp = SimplePickPlace(arm, IK(), BoardToRobot.load(), log=log)
    t = Transfer(piece, tuple(square_center_mm(chess.parse_square(src))), tuple(square_center_mm(chess.parse_square(dst))), f"{piece} {src}-{dst}")
    try:
        ok = pp.execute(t, home=home)
        if home and not isinstance(arm, FakeArm):
            pp.go_look()
        return ok
    except (GraspFailed, Unreachable) as e:
        log(f"  {e}")
        if home and not isinstance(arm, FakeArm):
            pp.go_look()
        return False
    finally:
        if own:
            arm.close()
