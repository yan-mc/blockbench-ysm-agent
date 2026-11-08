import json, os, math, time
import numpy as np
from PIL import Image
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
d = json.load(open(os.path.join(BASE, "pack", "models", "main.json"), encoding="utf-8"))
bones = {b["name"]: b for b in d["minecraft:geometry"][0]["bones"]}
parent = {b["name"]: b.get("parent") for b in d["minecraft:geometry"][0]["bones"]}
def under(n, root):
    while n:
        if n == root: return True
        n = parent.get(n)
    return False
names = [n for n in bones if under(n, "Hair")]
R = math.radians
def rotM(rot):
    a, b, c = (rot or [0, 0, 0]); a, b, c = R(a), R(b), R(c)
    ca, sa = math.cos(a), math.sin(a); cb, sb = math.cos(b), math.sin(b); cc, sc = math.cos(c), math.sin(c)
    return [[cb*cc, -cb*sc, sb], [ca*sc+sa*sb*cc, ca*cc-sa*sb*sc, -sa*cb], [sa*sc-ca*sb*cc, sa*cc+ca*sb*sc, ca*cb]]
def verts(c):
    o = c["origin"]; s = c["size"]; M = rotM(c.get("rotation"))
    cen = [o[i]+s[i]/2 for i in range(3)]; out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                p = [sx*s[0]/2, sy*s[1]/2, sz*s[2]/2]
                out.append([sum(M[i][j]*p[j] for j in range(3))+cen[i] for i in range(3)])
    return out
C = []
for n in names:
    for c in bones[n].get("cubes", []):
        vs = verts(c)
        lo = [min(v[i] for v in vs) for i in range(3)]; hi = [max(v[i] for v in vs) for i in range(3)]
        M = rotM(c.get("rotation")); o = c["origin"]; s = c["size"]
        cen = [o[i]+s[i]/2 for i in range(3)]
        C.append((M, cen, s, lo, hi))
def hit(x, z):
    best = None
    for M, cen, s, lo, hi in C:
        if x < lo[0] or x > hi[0] or z < lo[2] or z > hi[2]: continue
        px = [x-cen[0], 100-cen[1], z-cen[2]]
        pl = [M[0][j]*px[0]+M[1][j]*px[1]+M[2][j]*px[2] for j in range(3)]
        dl = [-M[1][0], -M[1][1], -M[1][2]]
        tmin, tmax = -1e9, 1e9; ok = True
        for i in range(3):
            hh = s[i]/2.0
            if abs(dl[i]) < 1e-9:
                if abs(pl[i]) > hh: ok = False; break
            else:
                t1 = (-hh-pl[i])/dl[i]; t2 = (hh-pl[i])/dl[i]
                if t1 > t2: t1, t2 = t2, t1
                tmin = max(tmin, t1); tmax = min(tmax, t2)
                if tmin > tmax: ok = False; break
        if ok and tmax >= 0:
            v = 100-tmax
            if best is None or v > best: best = v
    return best
im = Image.open(os.path.join(BASE, "artifacts", "v7f", "isolate-hair-top.png")).convert("RGBA")
a = np.array(im)[:, :, 3]
S = 300
scale = 2400//S
ra = a[::scale, ::scale][:S, :S]
rmask = ra > 8
sx = 121.79; cx = 1199.5; cz = 1321.5; zc0 = 1.005
t0 = time.time()
mine = np.zeros((S, S), bool)
for j in range(S):
    y_px = j*scale + scale/2
    z = zc0 - (y_px-cz)/sx
    for i in range(S):
        x_px = i*scale + scale/2
        x = (x_px-cx)/sx
        mine[j, i] = hit(x, z) is not None
print("done %.1fs" % (time.time()-t0))
dis = (mine != rmask)
print("cells", S*S, "disagree", int(dis.sum()))
# where render transparent but geometry opaque
bad = [(i*scale, j*scale) for j in range(S) for i in range(S) if rmask[j, i] is False and mine[j, i]]
good = [(i*scale, j*scale) for j in range(S) for i in range(S) if rmask[j, i] and not mine[j, i]]
print("render-transparent/geom-opaque:", len(bad), bad[:10])
print("render-opaque/geom-transparent:", len(good), good[:10])
