import json, os, math
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
P = os.path.join(BASE, "pack", "models", "main.json")
d = json.load(open(P, encoding="utf-8")); bones = {b["name"]: b for b in d["minecraft:geometry"][0]["bones"]}
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
names = ["HairCap", "front_h1", "corner_h1", "HairBack", "hl_side", "TwinTail_L", "TwinTail_R", "FLongHair", "MLongHair", "LongHair", "Ribbon", "HairBow_R"]
for probe in [(2.2, 0.2), (2.2, 1.0), (-2.2, 0.2), (1.7, 1.0), (2.6, 0.2), (2.2, 2.5), (2.2, -1.0)]:
    hits = []
    for n in names:
        for i, c in enumerate(bones[n].get("cubes", [])):
            t = ray(c, *probe)
            if t is not None: hits.append((round(t, 2), n, i))
    hits.sort(reverse=True)
    print(probe, "->", hits[:4], "| n=", len(hits))
