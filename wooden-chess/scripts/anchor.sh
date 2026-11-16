#!/usr/bin/env bash
# DEFAULT RECALIBRATION: teach one square centre by hand (fixed-finger tip, jaws closed), all 64 centres are then calculated (+30 mm steps). See calib/anchor_grid.py.
#   scripts/anchor.sh           (no arguments: teach c3 c6 f3 f6, each quadrant uses its own square)
#   scripts/anchor.sh a1 [h1]   (old one/two-square mode)
cd "$(dirname "$0")/.." && source scripts/env.sh
exec python -m chess_player.calib.anchor_grid "$@"
