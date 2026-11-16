"""DEFAULT RECALIBRATION: teach ONE square centre by hand (or two, for the board's rotation); every other centre = that plus 30 mm steps along the board's axes.

  scripts/anchor.sh               DEFAULT (no arguments): teach c3, c6, f3, f6; each quadrant (a-d/1-4, a-d/5-8, e-h/1-4, e-h/5-8) is calculated from ITS OWN taught square only (no averaging of positions; the rotation is fitted from the 4 points)
  scripts/anchor.sh a1 [h1]      old one/two-square mode, only if you name the squares

Torque goes OFF; you guide the TIP OF THE FIXED (stiff) FINGER, jaws closed, to the centre of the square and press Enter (for a second square: again).
All 64 entries of data/center_teach.json are rewritten (a dated copy is made first).
  one square : the board's axes come from the current data/board_to_robot.json
  two squares: the axes (rotation) come from the line between the two taught points, exact 30 mm pitch; a far pair (a1+h1, or a1+a8) is best
When the last square is taught the torque is switched OFF (hold the arm, then move it to the home pose by hand).
Entries hold the arm's real tip position in the robot frame (tip_robot_mm); motion/simple_pick_place.py turns them into the arm's targets.
"""
import json
import shutil
import sys
from datetime import datetime

import chess
import numpy as np

from chess_player import config as C
from chess_player.geometry import BoardToRobot, board_from_robot, square_center_mm
from chess_player.motion.arm import Arm, look_pose
from chess_player.motion.ik import IK

FILE = C.DATA / "center_teach.json"


def free_arm_keep_roll(arm):
    """Torque off on every joint EXCEPT the wrist roll, which is first driven to the playing roll and stays locked, so the touch is taken at the roll the arm plays with."""
    arm.hold()
    arm.move_to({"wrist_roll": C.WRIST_ROLL_DEG}, 2.0)
    with arm.lock:
        for j in C.ALL_JOINTS:
            if j != "wrist_roll":
                arm.bus.write("Torque_Enable", j, 0)
    arm.torque_on = False


def teach_point(arm, ik, sq):
    """Teach by hand; then the arm goes home and back to the taught pose on its own. Enter = keep, r = redo."""
    while True:
        free_arm_keep_roll(arm)
        print(f"Torque OFF (the wrist roll stays locked at {C.WRIST_ROLL_DEG:.1f} deg, the playing roll). Support the arm. Put the TIP OF THE FIXED FINGER (jaws closed) on the CENTRE of {sq.upper()}, then press Enter.")
        input()
        q = arm._read_present()
        arm.hold()
        print(f"Taught {sq.upper()}. The arm goes home and comes back to it by itself (keep clear)...")
        home = {**look_pose(), "gripper": C.GRIPPER_MIN_PCT}
        arm.move_to(home, 4.0)
        arm.move_to({j: q[j] for j in C.ALL_JOINTS if j != "gripper"} | {"gripper": C.GRIPPER_MIN_PCT}, 4.0)
        roll = float(q["wrist_roll"])
        print(f"  wrist roll at this touch {roll:.1f} deg, the arm plays at {C.WRIST_ROLL_DEG:.1f} deg" + (
              "   <-- DIFFERENT: the fingertip sits at another place at the playing roll, so the arm will be off. Press r and keep the roll." if abs(roll - C.WRIST_ROLL_DEG) > 3 else "  (ok)"))
        ans = input(f"The arm is on {sq.upper()}. Enter = keep, r = redo: ").strip().lower()
        if ans != "r":
            return q, ik.fk([q[j] for j in C.ARM_JOINTS])[:3, 3] * 1000.0
        print("Redo.")


def axes_from_calibration(T):
    """2x2 map (board mm step -> robot mm step), unit pitch, from today's board_to_robot (rotation + reflection only, no stretch)."""
    o = np.array(T(0.0, 0.0, 0.0)[:2]) * 1000.0
    ex = np.array(T(1.0, 0.0, 0.0)[:2]) * 1000.0 - o
    ey = np.array(T(0.0, 1.0, 0.0)[:2]) * 1000.0 - o
    return np.c_[ex / np.linalg.norm(ex), ey / np.linalg.norm(ey)]


QUAD_ANCHORS = ["c3", "c6", "f3", "f6"]  # a-d/1-4, a-d/5-8, e-h/1-4, e-h/5-8


def quad_anchor(s):
    """Which of the four taught squares owns square s (its quadrant)."""
    sq = chess.parse_square(s)
    return ("c" if chess.square_file(sq) < 4 else "f") + ("3" if chess.square_rank(sq) < 4 else "6")


def main():
    quad = len(sys.argv) == 1 or sys.argv[1].lower() == "quad"  # default: four quadrant anchors
    squares = QUAD_ANCHORS if quad else ([s.lower() for s in sys.argv[1:3]] or ["a1"])
    for s in squares:
        chess.parse_square(s)
    T, ik = BoardToRobot.load(), IK()
    arm = Arm(use_sag_model=False)
    taught = []
    try:
        for s in squares:
            taught.append(teach_point(arm, ik, s))
        while quad:  # sanity: the taught squares must be the ideal distance apart (30 mm pitch); a wrong point shifts a whole quadrant
            bad = []
            for i, j in [(0, 2), (1, 3), (0, 1), (2, 3)]:
                ideal = float(np.linalg.norm(np.array(square_center_mm(chess.parse_square(squares[j])), float) - np.array(square_center_mm(chess.parse_square(squares[i])), float)))
                got = float(np.linalg.norm(taught[j][1][:2] - taught[i][1][:2]))
                print(f"  {squares[i]}-{squares[j]}: taught {got:.1f} mm, ideal {ideal:.1f} mm" + ("   <-- OFF" if abs(got - ideal) > 6 else ""))
                if abs(got - ideal) > 6:
                    bad += [squares[i], squares[j]]
            if not bad:
                break
            ans = input(f"Some distances are off by more than 6 mm. Type the square(s) to re-teach ({' '.join(sorted(set(bad)))}), or just Enter to accept anyway: ").split()
            if not ans:
                break
            for a in ans:
                if a.lower() in squares:
                    taught[squares.index(a.lower())] = teach_point(arm, ik, a.lower())
    finally:
        print("\nTorque is going OFF now: HOLD THE ARM and bring it back to the home pose by hand.")
        try:
            arm.close(release=True)  # torque off so the arm can be moved home by hand
        except Exception as e:
            print(f"could not switch the torque off ({e}); use the dashboard 'Torque off' or power-cycle the arm")
    nom = [np.array(square_center_mm(chess.parse_square(s)), float) for s in squares]
    M = axes_from_calibration(T)
    if quad:
        us, vs = [], []
        for i, j in [(0, 2), (1, 3), (0, 1), (2, 3)]:  # c3-f3, c6-f6, c3-c6, f3-f6
            us.append(M @ (nom[j] - nom[i])); vs.append(taught[j][1][:2] - taught[i][1][:2])
        phi = np.arctan2(sum(u[0] * v[1] - u[1] * v[0] for u, v in zip(us, vs)), sum(u @ v for u, v in zip(us, vs)))
        R = np.array([[np.cos(phi), -np.sin(phi)], [np.sin(phi), np.cos(phi)]])
        M = R @ M
        print(f"quadrants: board rotated {np.degrees(phi):+.1f} deg from the calibration's axes (fitted over 4 taught pairs)")
        for (i, j), nm in zip([(0, 2), (1, 3), (0, 1), (2, 3)], ["c3-f3", "c6-f6", "c3-c6", "f3-f6"]):
            print(f"  {nm}: taught {np.linalg.norm(taught[j][1][:2] - taught[i][1][:2]):.1f} mm, ideal {np.linalg.norm(nom[j] - nom[i]):.1f} mm")
    elif len(squares) == 2:
        d_nom, d_rob = nom[1] - nom[0], taught[1][1][:2] - taught[0][1][:2]
        phi = np.arctan2(d_rob[1], d_rob[0]) - np.arctan2(*(M @ d_nom)[::-1])
        R = np.array([[np.cos(phi), -np.sin(phi)], [np.sin(phi), np.cos(phi)]])
        M = R @ M
        print(f"two squares: board rotated {np.degrees(phi):+.1f} deg from the calibration's axes; taught distance {np.linalg.norm(d_rob):.1f} mm, ideal {np.linalg.norm(d_nom):.1f} mm")
    anchor_q, anchor_p = taught[0]
    data = json.loads(FILE.read_text()) if FILE.exists() else {}
    if FILE.exists():
        (FILE.parent / "center_teach_backups").mkdir(exist_ok=True)
        shutil.copy(FILE, FILE.parent / "center_teach_backups" / f"center_teach.{datetime.now():%Y%m%d-%H%M%S}-before-anchor.json")
    now = datetime.now().isoformat(timespec="seconds")
    for s in (chess.square_name(i) for i in chess.SQUARES):
        n = np.array(square_center_mm(chess.parse_square(s)), float)
        k = squares.index(quad_anchor(s)) if quad else 0
        xy = taught[k][1][:2] + M @ (n - nom[k])
        data[s] = {"square": s, "when": now, "by": "anchor-" + "-".join(squares),
                   "tip_robot_mm": [round(float(xy[0]), 2), round(float(xy[1]), 2), round(float(taught[k][1][2]), 2)]}
    FILE.write_text(json.dumps(data, indent=1))
    r = lambda s: np.array(data[s]["tip_robot_mm"][:2])
    print(f"SUMMARY anchor {squares} tip {np.round(anchor_p[:2], 1).tolist()} mm; 64 centres written (a1-b1 {np.linalg.norm(r('a1') - r('b1')):.1f}, "
          f"a1-a2 {np.linalg.norm(r('a1') - r('a2')):.1f}, a1-h8 {np.linalg.norm(r('a1') - r('h8')):.1f} mm)")


if __name__ == "__main__":
    main()
