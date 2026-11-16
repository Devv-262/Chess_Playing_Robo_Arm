# instructions.md: calibrate and run the chess robot

Read [setup.md](setup.md) first if this is a new laptop. This file explains, step by step, how to use the robot day to day.

**Every terminal, every time:**

```bash
cd ~/Desktop/chess/wooden-chess
source scripts/env.sh
```

(The `scripts/*.sh` files do the `source` for you, but you need it for the `python -m ...` commands.) **Only one program can use the arm at a time.** Close any other chess tool before starting another.

---

## The big picture: what each step does

The arm has no idea where the board is. It only knows its own joint angles. Two measurements tie the world together:

1. **Camera grid** (`regrid.sh`). The fixed camera must know where the 64 squares are *in the picture*, so it can read the board and draw square names. Done on an **empty** board.
2. **Anchor teach** (`anchor.sh`). You guide the arm's fingertip by hand onto the centre of a few squares. From those, the robot computes where all 64 square centres are in *its own* coordinates (30 mm apart). This is what makes the arm land on the squares.

| Situation | What to do |
|---|---|
| New laptop, new desk, or the camera moved | `regrid.sh`, then `anchor.sh` |
| Board or arm got bumped or moved | `anchor.sh` |
| Just starting a session on an unchanged setup | Optionally check with `move.sh`, then play |
| Board height or tilt changed (different table, thicker board) | `recalibrate.sh --height` |

**Calibration does not last.** If anything moves (board, arm base, table), measure again. It only takes a few minutes.

**Safety first:** keep a hand near the arm's power switch whenever it moves. When torque is off the arm is limp and can fall, so support it with your hand.

---

## 1. Start the camera window

```bash
python scripts/livecam.py
```

A window shows the live board with the grid and the square names drawn on it. **Leave it running** in its own terminal. It also serves the camera to the other tools at `http://127.0.0.1:8771/video`, so no other program can open the webcam directly.

What to look at: the grid lines should sit on the real squares, rank 1 at the **top** of the picture (the robot's side), the h-file on the left and the a-file on the right.

Close the window (X) to stop it. If you do not need the camera (for example while running only `move.sh`), you can skip this step.

---

## 2. `regrid.sh`: re-make the camera grid

**When:** the first time, and whenever the camera or the board moved in the camera's picture.

**Before you run it:**
- **Empty board**, no pieces on it.
- The whole board fully visible in the camera picture.
- The board held down (taped), so it does not slide.
- Decent lighting; the scene should not be moving.

```bash
bash scripts/regrid.sh
```

What it does:
1. stops and restarts the camera window;
2. takes a median of 9 frames (this removes noise) and finds the 7x7 inner corners of the board with OpenCV;
3. works out which of the 8 possible orientations is right (rank 1 at the top, h-file on the left);
4. saves the grid to `data/ext_corners.json`;
5. restarts the camera window so it uses the new grid;
6. writes a check picture to `data/ext_corners_check.jpg`.

**Result:** `OK: grid saved, camera window restarted. Check data/ext_corners_check.jpg`. Open that picture and make sure the lines sit on the board's lines.

If it prints `grid NOT changed`, read the message above it. Typical causes: fewer than 49 corners found (the board is partly out of view, glare, or a piece is on the board), or a poor fit. Fix the cause and run it again. The old grid is left untouched when it fails, and each success makes a dated backup (`data/ext_corners.before-regrid-*.json`).

---

## 3. `anchor.sh`: teach the arm where the squares are

**This is the default calibration.** It replaces the old long procedure. You teach **four** squares by hand (**c3, c6, f3, f6**). Each quarter of the board is then calculated from its own taught square, using exact 30 mm steps.

**Before you run it:**
- Board in its final place and not going to move.
- The arm powered, the wrist roll as the program expects (it locks the roll for you).
- You know what the **fixed finger** is: the gripper has one stiff, fixed jaw and one that moves. Touch with the tip of the **fixed (stiff) finger**, with the jaws closed.

```bash
bash scripts/anchor.sh
```

What happens, for each of the four squares:
1. **Torque goes off** (the arm is limp, except the wrist roll, which stays locked at the playing angle). **Hold the arm.**
2. Move the arm by hand so that the **tip of the fixed finger touches the centre of the named square**. Eyeball the centre; your eye is the reference.
3. Press **Enter**.
4. The arm goes home and returns to that pose by itself, so you can see where it ended up. Keep clear.
5. **Enter = keep it**, **`r` = redo that square.**

Notes while teaching:
- The program prints the wrist roll at each touch. If it says `DIFFERENT`, the fingertip is not where it will be during play: press `r` and redo it without turning the wrist.
- After all four it prints the distances between your taught squares against the ideal ones. If any is off by more than **6 mm** it lists the squares and asks which ones to re-teach. Type the square names (for example `c6 f3`) to redo them, or just Enter to accept.
- At the end, **torque goes off again: hold the arm and put it in the home pose by hand.**
- The last line starts with `SUMMARY anchor ...` and says that 64 centres were written.

**Result:** all 64 square centres are saved in `data/center_teach.json` (a dated copy of the old file is made first).

**Variations:**
```bash
bash scripts/anchor.sh a1          # one square only (quick, but no rotation information)
bash scripts/anchor.sh a1 h1       # two far-apart squares: also measures the board's rotation
bash scripts/recalibrate.sh        # the same as anchor.sh, kept for habit
bash scripts/recalibrate.sh --grid # camera grid first (empty board), then the anchor teach
bash scripts/recalibrate.sh --height  # only if the board's height or tilt changed (see below)
```

**`--height`:** touches the four board corners to find the board's plane (`data/board_to_robot.json`), then does the normal anchor teach. Use it only when the table or board *height* or tilt changed. For an ordinary bump, plain `anchor.sh` is enough.

---

## 4. `move.sh`: pick up one piece and put it down

This is the **same motion the game uses**, so it is the best way to test the calibration.

```bash
bash scripts/move.sh p e2 e4
```

The three arguments are the **piece** (`p` pawn, `n` knight, `b` bishop, `r` rook, `q` queen, `k` king), the **from** square and the **to** square. Squares can be typed `e2` or `2e`. With no arguments the script asks you for them:

```bash
bash scripts/move.sh
```

**Before you run it:**
- Put **only that one piece** on the source square (no neighbours, so nothing gets knocked over).
- The destination is empty.
- **Hand near the power switch.** The program waits for you to press Enter before it goes.

What the arm does:
1. opens the gripper;
2. moves above the piece at carry height, goes straight down to the piece's grip height;
3. closes the gripper. If it closes almost fully (below 3 %), the hand is empty: it opens and retries up to 3 times;
4. lifts, carries the piece high above the other pieces, lowers, opens, goes straight up and returns home.

There is **no camera steering and no corrections**: it goes exactly to the taught centres plus the fixed piece-specific numbers in `data/wooden_grasps.json` (how high to grip, how tight to squeeze, the finger offset). If a pick is off, **recalibrate with `anchor.sh`; do not edit the numbers.**

Useful extras:
```bash
python -m chess_player.calib.simple_move p e2 e4 --dry-run   # simulated arm, nothing moves
python -m chess_player.calib.simple_move p e2 e4 --yes       # skip the "Enter = go" question
```

**A good check after calibrating:** `move.sh p c3 c4`, then `move.sh p f6 f5`, then a square far from the four taught ones (for example `a1` to `a2`, then `h8` to `h7`). The far ranks (7 and 8) tend to land a few millimetres short in Y.

---

## 5. Play a whole game

Needs the arm, the camera window, the trained YOLO model and Stockfish.

```bash
python scripts/livecam.py          # terminal 1: leave running
scripts/run_pipeline.sh            # terminal 2: starts everything and opens the dashboard
```

The dashboard is at **http://localhost:8770**. The game starts **paused**: press **Play** (or Space).

- The robot plays **white** and you play **black**. Place the pieces in the standard start position, white (robot) on rank 1.
- After each of your moves the camera reads the board with YOLO and checks your move is legal.
- Options: `scripts/run_pipeline.sh --dry-run` (simulated arm, no hardware), `--skill 0-20` (Stockfish strength).
- **Ctrl+C** in that terminal stops it. The arm stays holding at home.

Terminal-only version (no dashboard):
```bash
python -m chess_player.main --keyboard --robot-color white
```

**Before a game with promotions:** the spare queens go on the spots listed under `SPARES` in `src/chess_player/config.py`. Captured pieces are set down on 14 slots beside the board.

> **Known status (see `STATUS.md`):** `move.sh` and the anchor teach are the verified, reliable path. The game and dashboard still use the older grasp code and may miss grasps; treat whole games as experimental until they are switched over.

Read the board without playing:
```bash
python -m chess_player.vision.read_board
```

---

## 6. Other tools

| What | Command |
|---|---|
| Arm joint readout | `python -m tools.read_pose` |
| Make the arm limp (support it first!) | `python -m tools.release` |
| Hold the arm again | `python -m tools.torque` |
| Take training photos of the board, auto-labelled | `scripts/snap.sh` (camera window must be running) |
| Retrain YOLO | `python -m chess_player.vision.train_yolo --epochs 60 --batch 8` |
| Leader/follower teleoperation | `scripts/teleop.sh` |
| Recalibrate the servos themselves | `scripts/calibrate_follower.sh`, `scripts/calibrate_leader.sh` |

---

## 7. Recipes

**First time on a new laptop and desk**
```bash
python scripts/livecam.py                 # terminal 1: check the board is in view, then keep it open
bash scripts/regrid.sh                    # terminal 2: EMPTY board; look at data/ext_corners_check.jpg
bash scripts/anchor.sh                    # touch c3 c6 f3 f6 with the fixed finger
bash scripts/move.sh p e2 e4              # test with one pawn
```

**Something got bumped**
```bash
bash scripts/anchor.sh
bash scripts/move.sh p e2 e4
```

**The camera moved**
```bash
bash scripts/regrid.sh                    # empty board
```
(The arm does not depend on the camera for moves; the grid only affects board reading.)

---

## 8. Troubleshooting

| Problem | Cause and fix |
|---|---|
| The arm misses by several millimetres everywhere | The board or arm moved since the last anchor. Run `anchor.sh`. |
| It misses only on the far ranks | Known: ranks 7 and 8 undershoot a few millimetres in Y. Teach with the four-square anchor (default), not one square. |
| `regrid.sh`: `grid NOT changed` | Board not empty, partly out of view, glare, or too dark. Check `data/ext_corners_check.jpg`, fix, and re-run. |
| The pad lands on top of the piece's head | The fixed finger offset is part of the geometry; if the anchor was taught with the wrong finger, redo it with the **fixed** finger tip. |
| Anchor says wrist roll `DIFFERENT` | Press `r` and redo without turning the wrist. |
| Distances off by more than 6 mm after the four squares | Re-teach the named squares; take care to put the tip on the true centre. |
| `the camera window gave only N pictures` | `scripts/livecam.py` is not running, or the webcam is unplugged or in use. |
| Arm not responding / port busy | Another program holds the arm. Close it. Check `ls -l /dev/so100_follower`. |
| Arm limp and drooping | Torque is off. Run `python -m tools.torque` while supporting it, or re-run the script you wanted. |

More background, the history of every change and the lessons learned are in [STATUS.md](STATUS.md) and [commands.md](commands.md).
