import json, os, math
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
d = json.load(open(os.path.join(BASE, "pack", "models", "main.json"), encoding="utf-8"))
bc = {b["name"]: b for b in d["minecraft:geometry"][0]["bones"]}
cap = bc["HairCap"]["cubes"]
dome = cap[118:]
print("dome cubes", len(dome))
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
for probe in [(0, -3.6), (0, -3.4), (0, -2.6), (1.4, -2.6)]:
    hits = []
    for i, c in enumerate(cap):
        t = ray(c, *probe)
        if t is not None: hits.append((round(t, 2), i, "dome" if i >= 118 else "shell"))
    hits.sort(reverse=True)
    print(probe, "->", hits[:5])
# dome cube centers in the front half, sorted by z
fr = []
for i, c in enumerate(dome):
    o = c["origin"]; s = c["size"]
    cen = [o[j]+s[j]/2 for j in range(3)]
    fr.append((round(cen[2], 2), round(cen[1], 2), round(cen[0], 2), [round(v, 2) for v in s], c.get("rotation"), 118+i))
fr.sort()
print("\nfront-most dome cubes (z, y, x, size, rot, idx):")
for r in fr[:8]: print(" ", r)
print("\nall dome y-centre range:", round(min(f[1] for f in fr), 2), round(max(f[1] for f in fr), 2))
