import os, math
import numpy as np
from PIL import Image
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
def analyze(path, name):
    im = Image.open(path).convert("RGBA")
    a = np.array(im)[:, :, 3]
    ys, xs = np.nonzero(a > 8)
    cx, cy = (xs.min()+xs.max())/2, (ys.min()+ys.max())/2
    # fill holes: for each row inside bbox, count transparent runs bounded by opaque on both sides
    m = a > 8
    H, W = m.shape
    holes = 0
    hole_px = []
    for y in range(int(ys.min()), int(ys.max())+1):
        row = m[y]
        idx = np.nonzero(row)[0]
        if len(idx) < 2: continue
        lo, hi = idx[0], idx[-1]
        # transparent runs strictly inside
        sub = row[lo:hi+1]
        if sub.all(): continue
        # find runs of False
        z = np.nonzero(~sub)[0]
        # group
        if len(z) == 0: continue
        splits = np.split(z, np.nonzero(np.diff(z) > 1)[0]+1)
        for sp in splits:
            if len(sp) >= 2:
                holes += 1
                hole_px.append((y, int(lo+sp[0]), int(lo+sp[-1]), len(sp)))
    print(f"{name}: alpha bbox x[{xs.min()},{xs.max()}] y[{ys.min()},{ys.max()}] interior transparent runs={holes} total px={sum(h[3] for h in hole_px)}")
    if hole_px:
        s = sorted(hole_px, key=lambda t: -t[3])[:6]
        for h in s: print("   run y=%d x=%d..%d len=%d (center offset %.0f,%.0f)" % (h[0], h[1], h[2], h[3], (h[1]+h[2])/2-cx, h[0]-cy))
analyze(os.path.join(BASE, "artifacts", "v7e", "isolate-hair-top.png"), "v7e top")
analyze(os.path.join(BASE, "artifacts", "renders", "r0022", "top_2400.png"), "v7f top")
