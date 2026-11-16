"""ONE step: take a raw webcam photo, auto-label it with our YOLO, save image + editable YOLO label + preview. Nothing else to run afterwards.

  scripts/snap.sh                 a photo each time you press Enter (q + Enter quits)
  scripts/snap.sh --auto [secs]   a photo every N s (default 3) until Ctrl+C; frames identical to the last saved one are skipped (--all keeps them)
  scripts/snap.sh --conf 0.3
  scripts/snap.sh --redraw        rebuild every preview from the label files after you edited them

Saved in data/photos/labeled/:  images/<time>.jpg  labels/<time>.txt (class cx cy w h normalised; P N B R Q K p n b r q k, upper = white)
  preview/<time>.jpg (blue = white pieces, red = black pieces; preview only)   classes.txt  data.yaml (train: images, ready for YOLO training)
Edit labels with any YOLO labeller (labelImg / CVAT / Roboflow: open images/ + labels/), or edit the txt files. Existing labels are never overwritten.
The photo is the raw picture served by the camera window (scripts/livecam.py must be running), no grid drawn on it.
"""
import argparse, datetime, glob, os, sys, threading, time, urllib.request
import cv2
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from chess_player import config as C
from chess_player.vision import detect_board as D

URL = "http://127.0.0.1:8771/shot"
OUT = str(C.DATA / "photos" / "labeled")
BLUE, RED = (255, 0, 0), (0, 0, 255)  # BGR: white pieces blue, black pieces red
ap = argparse.ArgumentParser()
ap.add_argument("--auto", nargs="?", const=3.0, type=float, default=None, metavar="SECONDS", help="photo every N seconds (default 3) instead of on Enter")
ap.add_argument("--conf", type=float, default=0.25)
ap.add_argument("--all", action="store_true", help="keep frames even if the scene did not change")
ap.add_argument("--redraw", action="store_true")
a = ap.parse_args()
MANUAL = a.auto is None  # default: one photo per Enter
EVERY = a.auto or 3.0
for d in ("images", "labels", "preview"):
    os.makedirs(f"{OUT}/{d}", exist_ok=True)
CL = D.CLASSES


def iou(p, q):
    ix = max(0, min(p[2], q[2]) - max(p[0], q[0])); iy = max(0, min(p[3], q[3]) - max(p[1], q[1])); i = ix * iy
    return i / ((p[2] - p[0]) * (p[3] - p[1]) + (q[2] - q[0]) * (q[3] - q[1]) - i + 1e-9)


def draw(img, rows):
    vis = img.copy()
    for sym, c, (x1, y1, x2, y2) in rows:
        col = BLUE if sym.isupper() else RED
        cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), col, 2)
        cv2.putText(vis, sym if c is None else f"{sym} {c:.2f}", (int(x1), max(12, int(y1) - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2)
    return vis


def read_label(path, W, H):
    rows = []
    for l in open(path).read().split("\n"):
        if l.strip():
            k, cx, cy, w, h = l.split(); cx, cy, w, h = float(cx) * W, float(cy) * H, float(w) * W, float(h) * H
            rows.append((CL[int(k)], None, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)))
    return rows


def write_meta():
    open(f"{OUT}/classes.txt", "w").write("\n".join(CL) + "\n")
    open(f"{OUT}/data.yaml", "w").write(f"path: {os.path.abspath(OUT)}\ntrain: images\nval: images\nnames:\n" + "".join(f"  {i}: {c}\n" for i, c in enumerate(CL)))


if a.redraw:
    n = 0
    for f in sorted(glob.glob(f"{OUT}/images/*.jpg")):
        name = os.path.splitext(os.path.basename(f))[0]; lab = f"{OUT}/labels/{name}.txt"
        if os.path.exists(lab):
            img = cv2.imread(f); cv2.imwrite(f"{OUT}/preview/{name}.jpg", draw(img, read_label(lab, img.shape[1], img.shape[0]))); n += 1
    write_meta(); print(f"SUMMARY {n} previews redrawn"); sys.exit(0)

D.model(); S = D._symbols
try:
    urllib.request.urlopen(URL, timeout=3).read()
except Exception:
    sys.exit("camera window not running. Start it:  source scripts/env.sh && python scripts/livecam.py")


def grab():
    return cv2.imdecode(np.frombuffer(urllib.request.urlopen(URL, timeout=5).read(), np.uint8), cv2.IMREAD_COLOR)


def shoot(img):
    H, W = img.shape[:2]
    name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    cv2.imwrite(f"{OUT}/images/{name}.jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    r = D.predict(img, conf=a.conf, imgsz=C.ZOOM_IMGSZ)
    cand = sorted(((float(b.conf), S[int(b.cls)], b.xyxy[0].tolist()) for b in r.boxes if S[int(b.cls)]), reverse=True)
    rows = []
    for c, sym, bx in cand:  # drop duplicates: a lower-confidence box overlapping a kept one (any class) by IoU > 0.5
        if all(iou(bx, k[2]) <= 0.5 for k in rows):
            rows.append((sym, c, bx))
    lab = f"{OUT}/labels/{name}.txt"
    if not os.path.exists(lab):
        open(lab, "w").write("".join(f"{CL.index(s)} {(b[0]+b[2])/2/W:.6f} {(b[1]+b[3])/2/H:.6f} {(b[2]-b[0])/W:.6f} {(b[3]-b[1])/H:.6f}\n" for s, c, b in rows))
    cv2.imwrite(f"{OUT}/preview/{name}.jpg", draw(img, rows))
    return name, len(rows)


n, last = 0, None
write_meta()
print(f"Saving to {OUT}  ({'Enter = photo, q = quit' if MANUAL else f'every {EVERY:g}s, Ctrl+C to stop'})")
try:
    while True:
        if MANUAL:
            if input("> ").strip().lower() == "q":
                break
        img = grab()
        small = cv2.resize(img, (160, 90)).astype(np.float32)
        if not a.all and not MANUAL and last is not None and float(np.abs(small - last).mean()) < 2.0:
            print("  (same scene, skipped)"); time.sleep(EVERY); continue
        last = small
        name, k = shoot(img); n += 1
        print(f"  #{n} {name}: {k} pieces labelled")
        if not MANUAL:
            time.sleep(EVERY)
except KeyboardInterrupt:
    pass
print(f"\nSUMMARY {n} photos saved + labelled in {OUT}")
