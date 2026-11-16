#!/usr/bin/env bash
# See the auto-labelled photos one by one and fix the boxes with the mouse (keys listed at the top of scripts/review.py).
cd "$(dirname "$0")/.." && source scripts/env.sh
exec python scripts/review.py "$@"
