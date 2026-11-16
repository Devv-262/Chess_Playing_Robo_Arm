# Commands (current, 2026-11-10)

Every terminal: `cd ~/Desktop/chess/wooden-chess && source scripts/env.sh`. Only one program can use the arm at a time.

| What | Command |
|---|---|
| Recalibrate after anything moved: tip of the FIXED finger (jaws closed) on the centre of C3, C6, F3, F6 in turn, Enter each; every quadrant is calculated from its own square (+30 mm) | `scripts/anchor.sh` (or `scripts/recalibrate.sh`) |
| Same with two squares (also gets the board's rotation) | `scripts/recalibrate.sh a1 h1` |
| Camera grid again (EMPTY board; camera window must run) | `scripts/regrid.sh` |
| One pick and place (the SAME motion the game plays) | `scripts/move.sh p e2 e4` |
| Camera window (keep running) | `python scripts/livecam.py` |
| Whole game + dashboard (arm, camera, YOLO, Stockfish) | `scripts/run_pipeline.sh` (add `--dry-run` for a simulated arm) |
| Terminal-only game | `python -m chess_player.main --keyboard --robot-color white` |
| Read the board with YOLO | `python -m chess_player.vision.read_board` |
| Retrain YOLO (new camera viewpoint: capture positions first, `vision/capture_dataset.py`) | `python -m chess_player.vision.train_yolo --epochs 60 --batch 8` |
| Free the arm (torque off) / hold | `python -m tools.release` / `python -m tools.torque` |
| Only if the board's HEIGHT changed: 4-corner touch, then the anchor | `scripts/recalibrate.sh --height` |

Motion = `motion/simple_pick_place.py` (centres from `data/center_teach.json`, per-piece numbers in `data/wooden_grasps.json`); move planning = `motion/transfers.py`.
