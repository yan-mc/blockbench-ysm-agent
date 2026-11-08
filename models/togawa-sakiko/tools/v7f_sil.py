import json, os, math
from PIL import Image
import numpy as np
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
IMG = os.path.join(BASE, "artifacts", "v7e", "isolate-hair-top.png")
im = Image.open(IMG).convert("RGBA")
a = np.array(im)[:, :, 3]
ys, xs = np.nonzero(a > 8)
cx, cy = (xs.min()+xs.max())/2, (ys.min()+ys.max())/2
print("mask bbox x", xs.min(), xs.max(), "y", ys.min(), ys.max(), "center", cx, cy)
X = xs-cx; Y = ys-cy
r = np.hypot(X, Y); th = np.degrees(np.arctan2(-Y, X)) % 360
nb = 144
rr = np.zeros(nb); 
idx = (th/(360/nb)).astype(int) % nb
for k in range(nb):
    sel = idx == k
    if sel.any(): rr[k] = r[sel].max()
print("r min %.1f max %.1f ratio %.3f" % (rr.min(), rr.max(), rr.max()/rr.min()))
sm = np.convolve(np.r_[rr[-3:], rr, rr[:3]], np.ones(7)/7, mode="same")[3:-3]
print("circle mean radius %.1f  std %.1f" % (sm.mean(), sm.std()))
d = np.abs(np.diff(np.r_[rr, rr[0]]))
print("jag |dr| per 2.5deg: max %.1f mean %.1f  (px)" % (d.max(), d.mean()))
# per 15 deg table
print(" ".join("%d:%.0f" % (k*2.5, rr[k]) for k in range(0, nb, 6)))

# ---- offender cubes: vertices with r>5.1 ----
R = math.radians
def rotM(rot):
    a_, b_, c_ = (rot or [0, 0, 0]); a_, b_, c_ = R(a_), R(b_), R(c_)
    ca, sa = math.cos(a_), math.sin(a_); cb, sb = math.cos(b_), math.sin(b_); cc, sc = math.cos(c_), math.sin(c_)
    return [[cb*cc, -cb*sc, sb], [ca*sc + sa*sb*cc, ca*cc - sa*sb*sc, -sa*cb], [sa*sc - ca*sb*cc, sa*cc + ca*sb*sc, ca*cb]]
def verts(c):
    o = c["origin"]; s = c["size"]; M = rotM(c.get("rotation"))
    cen = [o[i]+s[i]/2 for i in range(3)]; out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                p = [sx*s[0]/2, sy*s[1]/2, sz*s[2]/2]
                out.append([sum(M[i][j]*p[j] for j in range(3))+cen[i] for i in range(3)])
    return out
d = json.load(open(os.path.join(BASE, "pack", "models", "main.json"), encoding="utf-8"))
G = d["minecraft:geometry"][0]; bc = {b["name"]: b for b in G["bones"]}
print("\n### cubes protruding: any vertex r>5.05 (HairCap + front_h1 + corner_h1)")
for nm in ("HairCap", "front_h1", "corner_h1"):
    for i, c in enumerate(bc[nm]["cubes"]):
        vs = verts(c)
        mr = max(math.hypot(v[0], v[2]) for v in vs)
        if mr > 5.05:
            lo = [min(v[j] for v in vs) for j in range(3)]; hi = [max(v[j] for v in vs) for j in range(3)]
            print(f"{nm}[{i}] r={mr:.2f} y[{lo[1]:.1f},{hi[1]:.1f}] x[{lo[0]:.1f},{hi[0]:.1f}] z[{lo[2]:.1f},{hi[2]:.1f}] size={[round(v,2) for v in c['size']]} rot={c.get('rotation')}")
