import json, os, math
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
P = os.path.join(BASE, "pack", "models", "main.json")
d = json.load(open(P, encoding="utf-8")); bc = {b["name"]: b for b in d["minecraft:geometry"][0]["bones"]}
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
cap = bc["HairCap"]["cubes"]
AX, BZ_B, BZ_F, H0, KK = 4.78, 4.80, 4.02, 42.36, 1.70
gr = 0.2
tops = {}
for i in range(-24, 25):
    for k in range(-24, 25):
        x, z = round(i*gr, 2), round(k*gr, 2)
        best = None; who = None
        for c in cap:
            t = ray(c, x, z)
            if t is not None and (best is None or t > best): best, who = t, c
        tops[(x, z)] = (best, who)
print("ASCII crown height map (z rows: -4.8 top -> +4.8 bottom ; x cols -4.8..+4.8), '#'=>=41.5 'o'=40.6-41.5 '-'=39.6-40.6 ' '=none/<39.6")
for k in range(24, -25, -1):
    line = ""
    for i in range(-24, 25):
        b, _ = tops[(round(i*gr, 2), round(k*gr, 2))]
        line += (" " if b is None or b < 39.6 else ("#" if b >= 41.5 else ("o" if b >= 40.6 else "-")))
    print(f"z={k*gr:5.1f} |{line}|")
# where are the big steps
worst = []
for (x, z), (v, _) in tops.items():
    for dx, dz in ((gr, 0), (0, gr)):
        w = tops.get((round(x+dx, 2), round(z+dz, 2)))
        if w and v is not None and w[0] is not None:
            worst.append((abs(v-w[0]), (x, z), round(v, 2), (round(x+dx, 2), round(z+dz, 2)), round(w[0], 2)))
worst.sort(reverse=True)
print("\nworst steps:", worst[:10])
cells_ok = []
for (x, z), (v, _) in tops.items():
    s = math.sqrt((x/AX)**2 + (z/(BZ_B if z >= 0 else BZ_F))**2)
    if s <= 0.97 and (v is None or v < 40.35):
        cells_ok.append((x, z, round(v, 2) if v is not None else None, round(40.0+0*1, 2)))
print("hole cells (<40.35, elliptic<=0.97):", len(cells_ok))
print(sorted(cells_ok)[:20])
# under-dome dips: cells >0.10 below ideal
dips = []
for (x, z), (v, _) in tops.items():
    s = math.sqrt((x/AX)**2 + (z/(BZ_B if z >= 0 else BZ_F))**2)
    if s <= 0.99 and v is not None:
        ideal = H0-KK*s*s
        if v < ideal-0.10: dips.append((x, z, round(v, 2), round(ideal, 2)))
print("cells >0.10 below ideal:", len(dips))
print(sorted(dips)[:24])
# None cells
none = [k for k, v in tops.items() if v[0] is None]
print("cells with no hair:", len(none), sorted(none)[:12], "...")
