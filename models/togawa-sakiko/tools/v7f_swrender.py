import json, os, math, time
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
P = os.path.join(BASE, "pack", "models", "main.json")
d = json.load(open(P, encoding="utf-8")); bones = {b["name"]: b for b in d["minecraft:geometry"][0]["bones"]}
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
cubes = []
for n in names:
    for c in bones[n].get("cubes", []):
        o = c["origin"]; s = c["size"]; M = rotM(c.get("rotation"))
        cen = [o[i]+s[i]/2 for i in range(3)]
        # AABB
        lo = [1e9]*3; hi = [-1e9]*3
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    p = [sx*s[0]/2, sy*s[1]/2, sz*s[2]/2]
                    w = [sum(M[i][j]*p[j] for j in range(3))+cen[i] for i in range(3)]
                    for i in range(3):
                        lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
        cubes.append((n, c, M, cen, s, lo, hi))
def ray_top(c, x, z):
    n, cc, M, cen, s, lo, hi = c
    if x < lo[0] or x > hi[0] or z < lo[2] or z > hi[2]: return None
    px = [x-cen[0], 100-cen[1], z-cen[2]]
    pl = [M[0][0]*px[0]+M[1][0]*px[1]+M[2][0]*px[2],
          M[0][1]*px[0]+M[1][1]*px[1]+M[2][1]*px[2],
          M[0][2]*px[0]+M[1][2]*px[1]+M[2][2]*px[2]]
    dl = [-M[1][0], -M[1][1], -M[1][2]]
    tmin, tmax = -1e9, 1e9
    for i in range(3):
        hh = s[i]/2.0
        if abs(dl[i]) < 1e-9:
            if abs(pl[i]) > hh: return None
        else:
            t1 = (-hh-pl[i])/dl[i]; t2 = (hh-pl[i])/dl[i]
            if t1 > t2: t1, t2 = t2, t1
            tmin = max(tmin, t1); tmax = min(tmax, t2)
            if tmin > tmax: return None
    if tmax < 0: return None
    return 100 - tmax
lo_x = min(c[5][0] for c in cubes); hi_x = max(c[6][0] for c in cubes)
lo_z = min(c[5][2] for c in cubes); hi_z = max(c[6][2] for c in cubes)
step = 0.04
xs = [lo_x + i*step for i in range(int((hi_x-lo_x)/step)+1)]
zs = [lo_z + i*step for i in range(int((hi_z-lo_z)/step)+1)]
t0 = time.time()
H = []
for z in zs:
    row = []
    for x in xs:
        best = None
        for c in cubes:
            t = ray_top(c, x, z)
            if t is not None and (best is None or t > best): best = t
        row.append(best)
    H.append(row)
print("rendered %dx%d in %.1fs" % (len(xs), len(zs), time.time()-t0))
# interior holes: cells with None that are enclosed (flood fill from border)
W = len(xs); Hh = len(zs)
mask = [[H[k][i] is None for i in range(W)] for k in range(Hh)]
seen = [[False]*W for _ in range(Hh)]
from collections import deque
dq = deque()
for i in range(W):
    for k in (0, Hh-1):
        if mask[k][i] and not seen[k][i]: seen[k][i] = True; dq.append((k, i))
for k in range(Hh):
    for i in (0, W-1):
        if mask[k][i] and not seen[k][i]: seen[k][i] = True; dq.append((k, i))
while dq:
    k, i = dq.popleft()
    for dk, di in ((1,0),(-1,0),(0,1),(0,-1)):
        nk, ni = k+dk, i+di
        if 0 <= nk < Hh and 0 <= ni < W and mask[nk][ni] and not seen[nk][ni]:
            seen[nk][ni] = True; dq.append((nk, ni))
enc = [(xs[i], zs[k]) for k in range(Hh) for i in range(W) if mask[k][i] and not seen[k][i]]
print("software top-down: enclosed empty cells =", len(enc))
if enc:
    xs_ = [p[0] for p in enc]; zs_ = [p[1] for p in enc]
    print("  bbox x[%.2f,%.2f] z[%.2f,%.2f]" % (min(xs_), max(xs_), min(zs_), max(zs_)))
