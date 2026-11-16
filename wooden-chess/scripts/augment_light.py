"""Make lighting variants of the TRAINING photos only (labels are unchanged, the boxes stay where they are).
  python scripts/augment_light.py <train_images_dir> <train_labels_dir>
Per photo it writes dull-yellow, warm-yellow, neutral-white, cool-white, bright and very-bright, dim and overexposed copies (images + label copies, suffix _L<name>).
"""
import os, sys, shutil, cv2, numpy as np
imgs, labs = sys.argv[1], sys.argv[2]
# (name, per-channel gain B,G,R, gamma, brightness add)
V = {
 "dullyellow": ((0.70, 0.88, 1.00), 1.15, -12),
 "warmyellow": ((0.78, 0.95, 1.10), 1.0, 0),
 "whitebright": ((1.05, 1.05, 1.05), 0.80, 18),
 "coolwhite":  ((1.12, 1.02, 0.92), 0.95, 6),
 "overexposed": ((1.0, 1.0, 1.0), 0.60, 35),
 "dim":        ((0.95, 0.98, 1.0), 1.50, -25),
}
def apply(img, gain, gamma, add):
    f = img.astype(np.float32) / 255.0
    f = np.power(np.clip(f, 0, 1), gamma) * 255.0
    f = f * np.array(gain, np.float32)[None, None, :] + add
    return np.clip(f, 0, 255).astype(np.uint8)
n = 0
for fn in sorted(os.listdir(imgs)):
    if "_L" in fn or not fn.endswith(".jpg"): continue
    base = fn[:-4]; img = cv2.imread(os.path.join(imgs, fn))
    for name, (g, ga, ad) in V.items():
        cv2.imwrite(os.path.join(imgs, f"{base}_L{name}.jpg"), apply(img, g, ga, ad), [cv2.IMWRITE_JPEG_QUALITY, 92])
        shutil.copy(os.path.join(labs, base + ".txt"), os.path.join(labs, f"{base}_L{name}.txt")); n += 1
print("wrote", n, "lighting copies")
