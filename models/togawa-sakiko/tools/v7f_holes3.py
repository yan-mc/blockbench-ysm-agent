import json, os, math
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
def ray(c, x, z):
    o = c["origin"]; s = c["size"]; M = rotM(c.get("rotation"))
    cen = [o[i]+s[i]/2 for i in range(3)]
    px = [x-cen[0], 100-cen[1], z-cen[2]]
    pl = [sum(M[i][j]*px[i] for i in range(3)) for j in range(3)]
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
cubes = []
for n in names:
    for c in bones[n].get("cubes", []): cubes.append((n, c))
print("hair bones", len(names), "hair cubes", len(cubes))
gr = 0.1
none_cells = []
low_cells = []
for i in range(-55, 56):
    for k in range(-55, 56):
        x, z = round(i*gr, 2), round(k*gr, 2)
        best = None
        for n, c in cubes:
            t = ray(c, x, z)
            if t is not None and (best is None or t > best): best = t
        if best is None: none_cells.append((x, z))
        elif best < 40.0: low_cells.append((x, z, round(best, 2)))
print("cells with NO hair (top-down):", len(none_cells))
print(sorted(none_cells)[:30])
print("cells with top<40.0:", len(low_cells))
print(sorted(low_cells)[:30])
