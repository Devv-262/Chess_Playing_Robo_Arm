#!/usr/bin/env bash
# ONE command: photo from the webcam -> auto-labelled with our YOLO -> saved (image + editable YOLO label + preview, blue = white pieces, red = black).
#   scripts/snap.sh            a photo each time you press Enter (q = quit)      scripts/snap.sh --auto [secs]   a photo every N s
#   scripts/snap.sh --redraw   rebuild previews after you edited labels         (more options: see scripts/snap.py)
# Needs the camera window running: source scripts/env.sh && python scripts/livecam.py
cd "$(dirname "$0")/.." && source scripts/env.sh
exec python scripts/snap.py "$@"
