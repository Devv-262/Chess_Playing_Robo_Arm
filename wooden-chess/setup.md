# setup.md: set the chess robot up on a new laptop

This gets a fresh Ubuntu laptop to the point where the arm moves and the camera works. After this, follow [instructions.md](instructions.md) to calibrate and play.

**What you need**
- Ubuntu 22.04 or 24.04 (x86-64). The scripts are written for Linux.
- An NVIDIA GPU is recommended. It is needed for fast YOLO (board reading) training; everything else runs without it.
- The SO-101 follower arm and (for teaching) the leader arm, each on USB with its own power supply.
- The fixed board camera (Ausha webcam, on a stand on the human's side, seeing the whole board).
- The 12 in wooden board (30 mm squares) and the wooden pieces.
- Internet for the first install (about 10 minutes, mostly downloads).

---

## 1. Get the code

```bash
sudo apt-get update && sudo apt-get install -y git
cd ~/Desktop
git clone https://github.com/Devv-262/Chess-Playing-Robotic-ARm.git chess
cd chess
```

If the repo has the project inside a `wooden-chess/` folder, go into it. **Every command in these docs is run from the folder that contains `scripts/`, `setup/`, `src/` and `data/`**:

```bash
cd ~/Desktop/chess/wooden-chess
```

(If `scripts/` is in the top folder in your clone, stay there instead.)

---

## 2. Install the Python environment

```bash
bash setup/install_ubuntu.sh
```

This script:
1. installs system packages (git, curl, ffmpeg, v4l-utils, libgl1, build tools, python3-venv);
2. creates a virtual environment at `./.venv` (every script uses it automatically);
3. installs PyTorch with CUDA 12.8, then the pinned packages in `setup/requirements-ubuntu.txt` (LeRobot with Feetech servo support, OpenCV, NumPy, python-chess, SciPy and others);
4. installs YOLO (ultralytics) and this project in editable mode;
5. runs `setup/download_models.sh`: Stockfish (the chess engine) into `bin/stockfish`, a voice model, and a pretrained chess YOLO model.

If the GPU driver is old, pick an older CUDA build: `TORCH_CUDA=cu126 bash setup/install_ubuntu.sh`.

The script prints a line like `torch ... | cuda available: True`. If it says `NO GPU`, the robot still works, but training YOLO will be slow.

**One extra package the script does not install.** The camera window uses Tk:

```bash
sudo apt-get install -y python3-tk
```

---

## 3. Plug in the arms and give them stable names

Plug in both arms (USB and power), then:

```bash
bash setup/migrate_calibration.sh
```

It will ask for your sudo password. It:
- copies the saved servo calibrations (`data/calibration_backup/my_follower.json` and `my_leader.json`) to `~/.cache/huggingface/lerobot/calibration/`;
- installs `setup/99-so100.rules` into `/etc/udev/rules.d/`, which creates the stable device names **`/dev/so100_follower`** and **`/dev/so100_leader`**;
- adds you to the `dialout` group (serial access without root).

**Log out and back in once** if the script says it added you to `dialout`.

**Your arms will have different serial numbers.** The rules file matches the boards by serial number, and the numbers in it belong to the original arms. On a different set of arms:

```bash
udevadm info -a -n /dev/ttyACM0 | grep serial     # repeat with ttyACM1
```

Use the board's own `ATTRS{serial}` (the line from the CH343 device, not the USB hub). Edit the two lines under "NEW rig" in `setup/99-so100.rules`, then run `bash setup/migrate_calibration.sh` again and re-plug the arms. Check:

```bash
ls -l /dev/so100_follower /dev/so100_leader
```

Which board is the follower? Unplug the leader and see which `ttyACM` remains. The follower is the arm that moves.

**If the arms were never calibrated with LeRobot** (a brand new arm, not the saved one), run these once:

```bash
bash scripts/calibrate_follower.sh
bash scripts/calibrate_leader.sh
```

They follow LeRobot's on-screen steps: move every joint through its full range. The saved calibration in `data/calibration_backup/` is only valid for the arm it was made on.

---

## 4. Cameras

The scripts refer to the cameras by their stable USB ids, which are the same on any laptop for the same camera models:

| Camera | Id used by the code | Where it lives |
|---|---|---|
| Fixed board camera (Ausha) | `/dev/v4l/by-id/usb-Ausha_Webcam_Ausha_Webcam-video-index0` | `scripts/livecam.py` (`DEV`), `scripts/env.sh` |
| Gripper camera (Sonix) | `/dev/v4l/by-id/usb-Sonix_Technology_Co.__Ltd._USB2.0_CAM1_USB2.0_CAM1-video-index0` | `src/chess_player/config.py` (`CAMERA`) |

Check that your cameras show up with the same names:

```bash
ls /dev/v4l/by-id/
v4l2-ctl --list-devices
```

If your webcam has a different name, edit `DEV` in `scripts/livecam.py` (and `GRIPPER_CAM` in `scripts/env.sh`) to match what `ls /dev/v4l/by-id/` shows.

---

## 5. The YOLO board-reading model (not stored in git)

`data/yolo/best.pt` is too big for git, so a fresh clone does not have it. The labelled photos it was trained on **are** in the repo (`data/dataset/`), so train it on the new laptop (about 2 minutes on a GPU):

```bash
source scripts/env.sh
python -m chess_player.vision.train_yolo --epochs 60 --batch 8
```

Alternatively copy `data/yolo/best.pt` from the old laptop (USB stick or `scp`). Either way it ends up at `data/yolo/best.pt`.

**If your camera is in a new place or your pieces look different**, the old photos will not match well. Capture new positions with `python -m chess_player.vision.capture_dataset`, then retrain. Not needed to just run `move.sh` or `anchor.sh`; the model is only for reading the board during a game.

---

## 6. Check everything works

Run these one at a time, from the project folder.

```bash
source scripts/env.sh
```
Expected: no errors. Your prompt now uses the project's Python.

```bash
python -m tools.read_pose
```
Expected: the arm's six joint angles. This proves the follower is connected on `/dev/so100_follower`. (Use `python src/tools/read_pose.py` if that form fails.)

```bash
ls bin/stockfish data/yolo/best.pt
```
Expected: both files exist.

```bash
python scripts/livecam.py
```
Expected: a window with the live board picture. Close it with the window's X. If it fails with a Tk or display error, install `python3-tk` (step 2).

A simulated game, with no arm at all, checks the software:

```bash
scripts/run_pipeline.sh --dry-run
```
Expected: a browser window opens (http://localhost:8770). The game starts paused; press Play.

---

## 7. What is stored in git and what is not

| Stored in the repo | Rebuilt on the new laptop |
|---|---|
| All code, scripts, setup files | `.venv` (step 2) |
| Labelled YOLO photos (`data/dataset/`) | `data/yolo/best.pt` (step 5) |
| Servo calibrations (`data/calibration_backup/`) | `bin/stockfish`, voice and pretrained models (step 2) |
| Saved taught centres, grasp numbers (`data/center_teach.json`, `data/wooden_grasps.json`) | **Must be re-measured, see below** |

**Important:** `data/center_teach.json`, `data/ext_corners*.json`, `data/board_to_robot.json` and `data/board_correction.json` describe where the board and camera were on the *old* desk. On a new desk, or after anything moves, they are wrong. Do not trust them. Follow [instructions.md](instructions.md): **camera grid first (`regrid.sh`), then the anchor teach (`anchor.sh`)**. That is a fresh, short measurement and it is the only thing that makes the arm land on the squares.

Next: [instructions.md](instructions.md).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Permission denied: /dev/ttyACM0` or `/dev/so100_follower` | Log out and in (dialout group), or `sudo chmod 666 /dev/ttyACM*` for now. |
| `/dev/so100_follower` does not exist | Wrong serial in `setup/99-so100.rules` (step 3), or the arm is off or unplugged. |
| Ubuntu steals the USB serial port | `sudo apt remove brltty`, then re-plug. |
| `ModuleNotFoundError: chess_player` | You did not run `source scripts/env.sh` in this terminal. |
| Camera window: `No module named tkinter` | `sudo apt-get install python3-tk` |
| Camera is busy | Only one program may open the webcam. Close other apps using it. The camera window shares it with the tools. |
| Only one program can use the arm at a time | Close any other chess tool, game or teach script first. |
