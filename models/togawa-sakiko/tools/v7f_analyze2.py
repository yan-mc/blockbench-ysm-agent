import json, os, math
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
P = os.path.join(BASE, "pack", "models", "main.json")
cur = json.load(open(P, encoding="utf-8"))
G = cur["minecraft:geometry"][0]
bc = {b["name"]: b for b in G["bones"]}
R = math.radians

def rotM(rot):
    a, b, c = (rot or [0, 0, 0])
    a, b, c = R(a), R(b), R(c)
    ca, sa = math.cos(a), math.sin(a); cb, sb = math.cos(b), math.sin(b); cc, sc = math.cos(c), math.sin(c)
    return [[cb*cc, -cb*sc, sb],
            [ca*sc + sa*sb*cc, ca*cc - sa*sb*sc, -sa*cb],
            [sa*sc - ca*sb*cc, sa*cc + ca*sb*sc, ca*cb]]

def aabb(c):
    o = c["origin"]; s = c["size"]; M = rotM(c.get("rotation"))
    cen = [o[i] + s[i]/2 for i in range(3)]
    lo = [1e9]*3; hi = [-1e9]*3
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                p = [sx*s[0]/2, sy*s[1]/2, sz*s[2]/2]
                w = [sum(M[i][j]*p[j] for j in range(3)) + cen[i] for i in range(3)]
                for i in range(3):
                    lo[i] = min(lo[i], w[i]); hi[i] = max(hi[i], w[i])
    return lo, hi

cap = bc["HairCap"]["cubes"]
rows = []
for i, c in enumerate(cap):
    lo, hi = aabb(c)
    rows.append((i, lo, hi, c))
rows.sort(key=lambda r: -r[2][1])
print("### HairCap top-20 by world top-y")
for (i, lo, hi, c) in rows[:20]:
    cx = (lo[0]+hi[0])/2; cz = (lo[2]+hi[2])/2
    print(f"i={i:3d} top={hi[1]:6.2f} bot={lo[1]:6.2f} x[{lo[0]:5.2f},{hi[0]:5.2f}] z[{lo[2]:5.2f},{hi[2]:5.2f}] r={math.hypot(cx,cz):4.2f} size={[round(v,2) for v in c['size']]} rot={c.get('rotation')}")

print("\n### kept shell cubes with top>40.9")
for (i, lo, hi, c) in rows:
    if hi[1] > 40.9 and i < 122:
        cx = (lo[0]+hi[0])/2; cz = (lo[2]+hi[2])/2
        print(f"i={i:3d} top={hi[1]:6.2f} bot={lo[1]:6.2f} r={math.hypot(cx,cz):4.2f} c=({cx:5.2f},{(lo[1]+hi[1])/2:6.2f},{cz:5.2f}) size={[round(v,2) for v in c['size']]} rot={c.get('rotation')}")

print("\n### kept shell: radial profile of TOP surface (max top by 0.5 r-band)")
import collections
band = collections.defaultdict(list)
for i, lo, hi, c in rows:
    if i >= 122: continue
    cx = (lo[0]+hi[0])/2; cz = (lo[2]+hi[2])/2
    band[round(math.hypot(cx, cz)*2)/2].append(hi[1])
for r in sorted(band):
    v = band[r]
    print(f" r={r:4.1f} n={len(v):2d} maxtop={max(v):6.2f} mintop={min(v):6.2f}")

print("\n### shell wall sample (8 cubes around)")
for i, lo, hi, c in rows:
    if i < 122 and abs((lo[1]+hi[1])/2 - 38) < 6 and i % 17 == 0:
        print(f"i={i:3d} y[{lo[1]:5.2f},{hi[1]:5.2f}] x[{lo[0]:5.2f},{hi[0]:5.2f}] z[{lo[2]:5.2f},{hi[2]:5.2f}] size={[round(v,2) for v in c['size']]} rot={c.get('rotation')}")

# Head bbox for reference
for nm in ("Head",):
    cs = bc[nm]["cubes"]
    lo = [1e9]*3; hi = [-1e9]*3
    for c in cs:
        l, h = aabb(c)
        for i in range(3): lo[i] = min(lo[i], l[i]); hi[i] = max(hi[i], h[i])
    print(f"\n{nm} world bbox {[round(v,2) for v in lo]} .. {[round(v,2) for v in hi]}")
