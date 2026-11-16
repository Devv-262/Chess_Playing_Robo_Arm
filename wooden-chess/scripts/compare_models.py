"""Compare two YOLO models on the SAME held-out, hand-checked photos (and on lighting-changed copies of them).

  python scripts/compare_models.py <wired_best.pt> <candidate_best.pt> <val_images_dir> <val_labels_dir> <report.md>

Both models are read through the game's own class mapping (detect_board._symbol), so differently named/ordered classes compare fairly.
Per class: precision / recall / F1 at conf 0.35 and IoU 0.5. Also: how many photos are read PERFECTLY (every box right, none extra, none missing).
Lighting: dull yellow, warm yellow, bright white, cool white, overexposed, dim (same recipes as scripts/augment_light.py), plus the plain photos.
"""
import glob, json, os, sys, collections
import cv2, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from ultralytics import YOLO
from chess_player.vision.detect_board import _symbol, CLASSES

W_PT, C_PT, IMGS, LABS, REPORT = sys.argv[1:6]
CONF, IOU_T = 0.35, 0.5
LIGHT = {
    "plain": None,
    "dull yellow": ((0.70, 0.88, 1.00), 1.15, -12),
    "warm yellow": ((0.78, 0.95, 1.10), 1.0, 0),
    "bright white": ((1.05, 1.05, 1.05), 0.80, 18),
    "cool white": ((1.12, 1.02, 0.92), 0.95, 6),
    "overexposed": ((1.0, 1.0, 1.0), 0.60, 35),
    "dim": ((0.95, 0.98, 1.0), 1.50, -25),
}


def light(img, spec):
    if spec is None:
        return img
    g, ga, ad = spec
    f = np.power(np.clip(img.astype(np.float32) / 255.0, 0, 1), ga) * 255.0
    return np.clip(f * np.array(g, np.float32)[None, None, :] + ad, 0, 255).astype(np.uint8)


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1])); i = ix * iy
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9)


def truth(name, W, H):
    out = []
    for l in open(os.path.join(LABS, name + ".txt")):
        if l.strip():
            k, cx, cy, w, h = l.split(); cx, cy, w, h = float(cx) * W, float(cy) * H, float(w) * W, float(h) * H
            out.append((CLASSES[int(k)], [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]))
    return out


def predict(model, symbols, img, imgsz):
    r = model.predict(img, conf=CONF, imgsz=imgsz, verbose=False)[0]
    out = []
    for b in r.boxes:
        s = symbols.get(int(b.cls))
        if s:
            out.append((s, b.xyxy[0].tolist(), float(b.conf)))
    return sorted(out, key=lambda x: -x[2])


def score(preds, gts, st):
    used = set(); perfect = True
    for s, bx, c in preds:
        best, bj = 0, None
        for j, (gs, gb) in enumerate(gts):
            if j in used:
                continue
            v = iou(bx, gb)
            if v > best:
                best, bj = v, j
        if bj is not None and best >= IOU_T and gts[bj][0] == s:
            used.add(bj); st[s]["tp"] += 1
        else:
            st[s]["fp"] += 1; perfect = False
    for j, (gs, gb) in enumerate(gts):
        if j not in used:
            st[gs]["fn"] += 1; perfect = False
    return perfect


def evaluate(pt, imgsz):
    m = YOLO(pt); sym = {i: _symbol(n) for i, n in m.names.items()}
    res = {}
    names = sorted(os.path.splitext(os.path.basename(f))[0] for f in glob.glob(IMGS + "/*.jpg"))
    for ln, spec in LIGHT.items():
        st = collections.defaultdict(lambda: collections.Counter()); perf = 0
        for n in names:
            img = cv2.imread(os.path.join(IMGS, n + ".jpg")); H, W = img.shape[:2]
            perf += score(predict(m, sym, light(img, spec), imgsz), truth(n, W, H), st)
        res[ln] = (st, perf, len(names))
    return res


def prf(c):
    p = c["tp"] / max(1, c["tp"] + c["fp"]); r = c["tp"] / max(1, c["tp"] + c["fn"]); f = 2 * p * r / max(1e-9, p + r)
    return p, r, f


def total(st):
    t = collections.Counter()
    for c in st.values():
        t.update(c)
    return t


lines = ["# Model comparison on held-out, hand-checked photos", "",
         f"- wired-in model: `{W_PT}`", f"- candidate: `{C_PT}`", f"- photos: {len(glob.glob(IMGS + '/*.jpg'))} (never used for training either model)",
         f"- conf {CONF}, IoU {IOU_T}. 'perfect photo' = every piece boxed with the right class, nothing extra, nothing missing.", ""]
allres = {}
for imgsz in (960, 1280, 1920):
    allres[imgsz] = (evaluate(W_PT, imgsz), evaluate(C_PT, imgsz))
for imgsz, (rw, rc) in allres.items():
    lines += [f"## Inference size {imgsz}", "", "| lighting | wired F1 | candidate F1 | wired perfect photos | candidate perfect photos |", "|---|---|---|---|---|"]
    for ln in LIGHT:
        a, b = total(rw[ln][0]), total(rc[ln][0])
        lines.append(f"| {ln} | {prf(a)[2]:.3f} | {prf(b)[2]:.3f} | {rw[ln][1]}/{rw[ln][2]} | {rc[ln][1]}/{rc[ln][2]} |")
    lines.append("")
rw, rc = allres[1280]
lines += ["## Per piece type (plain photos, inference size 1280)", "", "| piece | wired P | wired R | wired F1 | candidate P | candidate R | candidate F1 | boxes in truth |", "|---|---|---|---|---|---|---|---|"]
for c in CLASSES:
    a, b = prf(rw["plain"][0][c]), prf(rc["plain"][0][c]); n = rc["plain"][0][c]["tp"] + rc["plain"][0][c]["fn"]
    lines.append(f"| {c} | {a[0]:.2f} | {a[1]:.2f} | {a[2]:.2f} | {b[0]:.2f} | {b[1]:.2f} | {b[2]:.2f} | {n} |")
open(REPORT, "w").write("\n".join(lines) + "\n")
json.dump({str(k): {"wired": {ln: [dict(v) for v in [total(r[ln][0])]] for ln in LIGHT}, "cand": {ln: [dict(v) for v in [total(rc2[ln][0])]] for ln in LIGHT}} for k, (r, rc2) in allres.items()},
          open(REPORT.replace(".md", ".json"), "w"))
print("\n".join(lines))
