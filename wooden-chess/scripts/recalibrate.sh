#!/usr/bin/env bash
# Recalibrate after the board / arm / camera moved. DEFAULT = teach FOUR squares by hand (c3 c6 f3 f6), each quadrant of the board is calculated from its own square (+30 mm steps).
#   bash scripts/recalibrate.sh                 four quadrant anchors (torque off, fixed-finger tip on the centre of each, Enter)
#   bash scripts/recalibrate.sh a1 h1           two squares: also gets the board's rotation (best after turning the board)
#   bash scripts/recalibrate.sh --grid [...]    first re-make the camera grid (EMPTY board), then the above
#   bash scripts/recalibrate.sh --height        only if the board's HEIGHT/tilt changed: 4-corner touch (board_to_robot.json), then do the default
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1
source scripts/env.sh
ARGS=()
for a in "$@"; do
  case "$a" in
    --grid) bash scripts/regrid.sh || { echo "grid failed: fix that first"; exit 1; } ;;
    --height) python -m chess_player.calib.board_to_robot || exit 1 ;;
    *) ARGS+=("$a") ;;
  esac
done
exec python -m chess_player.calib.anchor_grid "${ARGS[@]}"
