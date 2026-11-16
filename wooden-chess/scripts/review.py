"""Look at the auto-labelled photos one by one and fix the boxes with the mouse.   scripts/review.sh

  Left / Right        previous / next photo (saves automatically)        Space  mark photo as checked + next (starts at the first unchecked)
  click a box         select it (corner handles appear); drag inside = move, drag a corner = resize
  drag on empty area  draw a NEW box (then press the piece letter to set its class)
  letter key          set the selected box's class:  capital = WHITE piece (P N B R Q K), small = BLACK (p n b r q k)
  Delete / BackSpace / right-click on a box    delete the box          Esc  deselect          s  save now
Blue box = white piece, red box = black piece. Labels live in data/photos/labeled/labels/*.txt (YOLO format), checked photos in reviewed.txt.
"""
import base64, glob, os, sys
import tkinter as tk
import cv2
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from chess_player import config as C

OUT = str(C.DATA / "photos" / "labeled")
CL = ["P", "N", "B", "R", "Q", "K", "p", "n", "b", "r", "q", "k"]
NAMES = dict(P="pawn", N="knight", B="bishop", R="rook", Q="queen", K="king")
BLUE, RED = "#2060ff", "#ff2020"
files = sorted(glob.glob(f"{OUT}/images/*.jpg"))
if not files:
    sys.exit("no photos yet: run scripts/snap.sh first")
RV = f"{OUT}/reviewed.txt"
reviewed = set(open(RV).read().split()) if os.path.exists(RV) else set()


class App:
    def __init__(self):
        self.root = tk.Tk()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        img0 = cv2.imread(files[0]); self.H, self.W = img0.shape[:2]
        self.sc = min(1.0, (sw - 40) / self.W, (sh - 140) / self.H)
        self.cv = tk.Canvas(self.root, width=int(self.W * self.sc), height=int(self.H * self.sc), highlightthickness=0, bg="black")
        self.cv.pack()
        self.info = tk.Label(self.root, text="", font=("Helvetica", 12), anchor="w"); self.info.pack(fill="x")
        self.i = next((k for k, f in enumerate(files) if self.name(f) not in reviewed), 0)
        self.sel = None; self.mode = None; self.dirty = False
        for ev, fn in (("<ButtonPress-1>", self.press), ("<B1-Motion>", self.drag), ("<ButtonRelease-1>", self.release), ("<Button-3>", self.rclick),
                       ("<Left>", lambda e: self.go(-1)), ("<Right>", lambda e: self.go(1)), ("<space>", self.check),
                       ("<Delete>", self.delete), ("<BackSpace>", self.delete), ("<Escape>", lambda e: self.select(None)), ("<Key>", self.key)):
            (self.cv if ev.startswith("<B") else self.root).bind(ev, fn)
        self.cv.bind("<ButtonPress-1>", self.press); self.cv.focus_set()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.load(); self.root.mainloop()

    name = staticmethod(lambda f: os.path.splitext(os.path.basename(f))[0])

    # ---------- files
    def load(self):
        f = files[self.i]; self.img = cv2.imread(f); self.H, self.W = self.img.shape[:2]
        disp = cv2.resize(self.img, (int(self.W * self.sc), int(self.H * self.sc)), interpolation=cv2.INTER_AREA)
        self.photo = tk.PhotoImage(data=base64.b64encode(cv2.imencode(".png", disp)[1].tobytes()))
        self.boxes = []; lab = f"{OUT}/labels/{self.name(f)}.txt"
        if os.path.exists(lab):
            for l in open(lab).read().split("\n"):
                if l.strip():
                    k, cx, cy, w, h = l.split(); cx, cy, w, h = float(cx) * self.W, float(cy) * self.H, float(w) * self.W, float(h) * self.H
                    self.boxes.append([CL[int(k)], cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2])
        self.sel = None; self.dirty = False; self.redraw()

    def save(self):
        if not self.dirty:
            return
        f = files[self.i]; n = self.name(f)
        open(f"{OUT}/labels/{n}.txt", "w").write("".join(
            f"{CL.index(c)} {(x1+x2)/2/self.W:.6f} {(y1+y2)/2/self.H:.6f} {(x2-x1)/self.W:.6f} {(y2-y1)/self.H:.6f}\n" for c, x1, y1, x2, y2 in self.boxes))
        vis = self.img.copy()
        for c, x1, y1, x2, y2 in self.boxes:
            col = (255, 32, 32) if c.isupper() else (32, 32, 255)
            cv2.rectangle(vis, (int(x1), int(y1)), (int(x2), int(y2)), col, 2)
            cv2.putText(vis, c, (int(x1), max(12, int(y1) - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, col, 2)
        cv2.imwrite(f"{OUT}/preview/{n}.jpg", vis); self.dirty = False

    def go(self, d):
        self.save(); self.i = (self.i + d) % len(files); self.load()

    def check(self, e=None):
        self.save(); reviewed.add(self.name(files[self.i])); open(RV, "w").write("\n".join(sorted(reviewed)) + "\n")
        self.i = next((k for k in list(range(self.i + 1, len(files))) + list(range(0, self.i + 1)) if self.name(files[k]) not in reviewed), self.i)
        self.load()

    def quit(self):
        self.save(); self.root.destroy()

    # ---------- drawing
    def redraw(self):
        c, s = self.cv, self.sc
        c.delete("all"); c.create_image(0, 0, anchor="nw", image=self.photo)
        for k, (cl, x1, y1, x2, y2) in enumerate(self.boxes):
            col = BLUE if cl.isupper() else RED; on = k == self.sel
            c.create_rectangle(x1 * s, y1 * s, x2 * s, y2 * s, outline=col, width=4 if on else 2)
            c.create_text(x1 * s + 2, y1 * s - 8, text=cl, fill=col, anchor="w", font=("Helvetica", 13, "bold"))
            if on:
                for hx, hy in ((x1, y1), (x2, y1), (x1, y2), (x2, y2)):
                    c.create_rectangle(hx * s - 5, hy * s - 5, hx * s + 5, hy * s + 5, fill="white", outline=col)
        f = files[self.i]; ok = "checked" if self.name(f) in reviewed else "NOT checked"
        sel = f"   selected: {self.boxes[self.sel][0]} ({NAMES[self.boxes[self.sel][0].upper()]}, {'white' if self.boxes[self.sel][0].isupper() else 'black'})" if self.sel is not None else ""
        self.info.config(text=f"{self.i+1}/{len(files)}  {self.name(f)}  {len(self.boxes)} boxes  [{ok}]{sel}      "
                              f"arrows=prev/next  space=checked+next  drag=move/new  corner=resize  letter=class (Capital=white)  Del=delete")
        self.root.title(f"review {self.i+1}/{len(files)}")

    def select(self, k):
        self.sel = k; self.redraw()

    # ---------- mouse
    def hit(self, x, y):
        best = None
        for k, (_, x1, y1, x2, y2) in enumerate(self.boxes):
            if x1 <= x <= x2 and y1 <= y <= y2 and (best is None or (x2 - x1) * (y2 - y1) < best[0]):
                best = ((x2 - x1) * (y2 - y1), k)
        return None if best is None else best[1]

    def press(self, e):
        self.cv.focus_set(); x, y = e.x / self.sc, e.y / self.sc; self.mode = None; r = 8 / self.sc
        if self.sel is not None:
            _, x1, y1, x2, y2 = self.boxes[self.sel]
            for ax, ay, fx, fy in ((x1, y1, x2, y2), (x2, y1, x1, y2), (x1, y2, x2, y1), (x2, y2, x1, y1)):
                if abs(x - ax) < r and abs(y - ay) < r:
                    self.mode = ("resize", fx, fy); return
        k = self.hit(x, y)
        if k is not None:
            self.sel = k; self.mode = ("move", x, y); self.redraw()
        else:
            self.sel = None; self.mode = ("new", x, y); self.redraw()

    def drag(self, e):
        if not self.mode:
            return
        x, y = min(max(e.x / self.sc, 0), self.W), min(max(e.y / self.sc, 0), self.H); m = self.mode[0]
        if m == "move":
            dx, dy = x - self.mode[1], y - self.mode[2]; b = self.boxes[self.sel]
            dx = max(-b[1], min(self.W - b[3], dx)); dy = max(-b[2], min(self.H - b[4], dy))
            b[1] += dx; b[3] += dx; b[2] += dy; b[4] += dy; self.mode = ("move", x, y); self.dirty = True; self.redraw()
        elif m == "resize":
            b = self.boxes[self.sel]; fx, fy = self.mode[1], self.mode[2]
            b[1], b[3], b[2], b[4] = min(x, fx), max(x, fx), min(y, fy), max(y, fy); self.dirty = True; self.redraw()
        else:
            self.redraw(); s = self.sc
            self.cv.create_rectangle(self.mode[1] * s, self.mode[2] * s, x * s, y * s, outline="yellow", dash=(4, 3), width=2)

    def release(self, e):
        if not self.mode:
            return
        if self.mode[0] == "new":
            x, y = min(max(e.x / self.sc, 0), self.W), min(max(e.y / self.sc, 0), self.H); x0, y0 = self.mode[1], self.mode[2]
            if abs(x - x0) > 8 and abs(y - y0) > 8:
                self.boxes.append(["P", min(x, x0), min(y, y0), max(x, x0), max(y, y0)]); self.sel = len(self.boxes) - 1; self.dirty = True
        self.mode = None; self.redraw()

    def rclick(self, e):
        k = self.hit(e.x / self.sc, e.y / self.sc)
        if k is not None:
            del self.boxes[k]; self.sel = None; self.dirty = True; self.redraw()

    # ---------- keys
    def delete(self, e=None):
        if self.sel is not None:
            del self.boxes[self.sel]; self.sel = None; self.dirty = True; self.redraw()

    def key(self, e):
        if e.char == "s":
            self.save(); return
        if e.char in CL and self.sel is not None:
            self.boxes[self.sel][0] = e.char; self.dirty = True; self.redraw()


App()
