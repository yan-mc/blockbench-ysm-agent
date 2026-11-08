import os
import numpy as np
from PIL import Image
from collections import deque
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"

def holes(path, name, scale=2):
    im = Image.open(path).convert("RGBA")
    a = np.array(im)[:, :, 3]
    a = a[::scale, ::scale]
    m = a > 8
    H, W = m.shape
    seen = np.zeros((H, W), bool)
    dq = deque()
    for x in range(W):
        for y in (0, H-1):
            if not m[y, x] and not seen[y, x]: seen[y, x] = True; dq.append((y, x))
    for y in range(H):
        for x in (0, W-1):
            if not m[y, x] and not seen[y, x]: seen[y, x] = True; dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y+dy, x+dx
            if 0 <= ny < H and 0 <= nx < W and not m[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True; dq.append((ny, nx))
    enclosed = (~m) & (~seen)
    n = int(enclosed.sum())
    print(f"{name}: enclosed transparent px={n} ({n*scale*scale} full-res px)")
    if n:
        ys, xs = np.nonzero(enclosed)
        # cluster by simple grid rounding
        pts = sorted(zip(ys.tolist(), xs.tolist()))
        comps = []
        used = set(pts)
        for p in pts:
            if p not in used: continue
            q = [p]; used.discard(p); comp = []
            while q:
                cy, cx = q.pop(); comp.append((cy, cx))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        np_ = (cy+dy, cx+dx)
                        if np_ in used:
                            used.discard(np_); q.append(np_)
            comps.append(comp)
        comps.sort(key=len, reverse=True)
        print("   clusters:", len(comps))
        for c in comps[:8]:
            ys_ = [p[0] for p in c]; xs_ = [p[1] for p in c]
            print("    px=%d  x[%d..%d] y[%d..%d]" % (len(c), min(xs_)*scale, max(xs_)*scale, min(ys_)*scale, max(ys_)*scale))
holes(os.path.join(BASE, "artifacts", "v7e", "isolate-hair-top.png"), "v7e top")
holes(os.path.join(BASE, "artifacts", "v7f", "isolate-hair-top.png"), "v7f top")

