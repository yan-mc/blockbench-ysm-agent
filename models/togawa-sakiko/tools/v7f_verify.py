import json, os, math, hashlib
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
P = os.path.join(BASE, "pack", "models", "main.json")
OLD = os.path.join(BASE, "artifacts", "v7f", "_presave", "main_v7e.json")
new = json.load(open(P, encoding="utf-8")); old = json.load(open(OLD, encoding="utf-8"))
gn = {b["name"]: b for b in new["minecraft:geometry"][0]["bones"]}
go = {b["name"]: b for b in old["minecraft:geometry"][0]["bones"]}
R = math.radians

print("== counts ==")
tn = sum(len(b.get("cubes", [])) for b in gn.values())
to = sum(len(b.get("cubes", [])) for b in go.values())
print("bones", len(gn), len(go), "| cubes", tn, to, "| animations",
      len(new.get("animations", [])), len(old.get("animations", [])))
CHANGED = ("HairCap", "front_h1", "HairBack", "hl_side")
h = lambda c: hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()[:12]
diff = [n for n in gn if h(gn[n].get("cubes")) != h(go[n].get("cubes")) or gn[n].get("pivot") != go[n].get("pivot")]
print("bones whose cubes changed:", diff)
print("front_h1 identical:", h(gn["front_h1"]["cubes"]) == h(go["front_h1"]["cubes"]))

def rotM(rot):
    a, b, c = (rot or [0, 0, 0]); a, b, c = R(a), R(b), R(c)
    ca, sa = math.cos(a), math.sin(a); cb, sb = math.cos(b), math.sin(b); cc, sc = math.cos(c), math.sin(c)
    return [[cb*cc, -cb*sc, sb], [ca*sc+sa*sb*cc, ca*cc-sa*sb*sc, -sa*cb], [sa*sc-ca*sb*cc, sa*cc+ca*sb*sc, ca*cb]]

def ray(c, x, z):
    o = c["origin"]; s = c["size"]; M = rotM(c.get("rotation"))
    cen = [o[i]+s[i]/2 for i in range(3)]
    px = [x-cen[0], 100-cen[1], z-cen[2]]
    pl = [sum(M[i][0]*px[i] for i in range(3)), sum(M[i][1]*px[i] for i in range(3)), sum(M[i][2]*px[i] for i in range(3))]
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

cap = gn["HairCap"]["cubes"]
shell = cap[:118]; dome = cap[118:]
AX, BZ_B, BZ_F, H0, KK = 4.78, 4.80, 4.02, 42.36, 1.70
def ideal(x, z):
    s = math.sqrt((x/AX)**2 + (z/(BZ_B if z >= 0 else BZ_F))**2)
    return H0-KK*s*s if s <= 1.0 else None

print("\n== crown height field (0.2 grid) ==")
gr = 0.2
tops = {}; hd = 0; hmin = 99; poke = []
for i in range(-35, 36):
    for k in range(-35, 36):
        x, z = i*gr, k*gr
        best = None; bestc = None
        for c in cap:
            t = ray(c, x, z)
            if t is not None and (best is None or t > best): best, bestc = t, c
        tops[(round(x, 2), round(z, 2))] = best
        s = math.sqrt((x/AX)**2 + (z/(BZ_B if z >= 0 else BZ_F))**2)
        if s <= 0.97:
            if best is None or best < 40.35: hd += 1; hmin = min(hmin, best or 0)
            ideal_h = H0-KK*s*s
            if best is not None and best > ideal_h+0.03: poke.append((round(x, 2), round(z, 2), round(best-ideal_h, 2)))
print("hole cells (elliptic r<=0.97, top<40.35):", hd, "lowest top:", (round(hmin, 2) if hd else "n/a"))
print("cells above ideal dome by >0.03:", len(poke), sorted(poke, key=lambda t: -t[2])[:8])
steps = []
for (x, z), v in tops.items():
    if v is None: continue
    for dx, dz in ((gr, 0), (0, gr)):
        w = tops.get((round(x+dx, 2), round(z+dz, 2)))
        if w is not None: steps.append(abs(v-w))
steps.sort()
print(f"adjacent step: max={steps[-1]:.2f} p99={steps[int(len(steps)*.99)]:.2f} p95={steps[int(len(steps)*.95)]:.2f} | >0.25: {sum(1 for s in steps if s > 0.25)} / {len(steps)}")

print("\n== protrusion (HairCap max radius) ==")
def verts(c):
    o = c["origin"]; s = c["size"]; M = rotM(c.get("rotation"))
    cen = [o[i]+s[i]/2 for i in range(3)]; out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                p = [sx*s[0]/2, sy*s[1]/2, sz*s[2]/2]
                out.append([sum(M[i][j]*p[j] for j in range(3))+cen[i] for i in range(3)])
    return out
mr = 0; arg = None
for nm in ("HairCap",):
    for c in gn[nm]["cubes"]:
        r = max(math.hypot(v[0], v[2]) for v in verts(c))
        if r > mr: mr, arg = r, c
print("HairCap max r new = %.2f" % mr, "| old = %.2f" % max(max(math.hypot(v[0], v[2]) for v in verts(c)) for c in go["HairCap"]["cubes"]))
print("apex top:", round(max(v[1] for c in gn["HairCap"]["cubes"] for v in verts(c)), 2),
      "| old:", round(max(v[1] for c in go["HairCap"]["cubes"] for v in verts(c)), 2))
# support function (convex silhouette) of HairCap only
pts = [(v[0], v[2]) for c in gn["HairCap"]["cubes"] for v in verts(c)]
rr = [max(x*math.cos(R(5*k))+z*math.sin(R(5*k)) for x, z in pts) for k in range(72)]
print("support r: min %.2f max %.2f ratio %.3f (old %.3f)" % (
    min(rr), max(rr), max(rr)/min(rr),
    (lambda rr2: max(rr2)/min(rr2))([max(x*math.cos(R(5*k))+z*math.sin(R(5*k)) for x, z in
                                     [(v[0], v[2]) for c in go["HairCap"]["cubes"] for v in verts(c)]) for k in range(72)])))

print("\n== strands ==")
for nm in ("HairBack", "hl_side"):
    cs = gn[nm]["cubes"]
    strands = []
    for c in cs:
        if abs((c.get("rotation") or [0])[0]) < 1e-9 and abs(c["size"][0]-1.2) < 1e-9:
            continue
        strands.append(c)
    print(nm, "cubes", len(cs))
# tips of back hair per lock: group by rounded x at the top
hb = gn["HairBack"]["cubes"]
print("HairBack y range:", round(min(min(v[1] for v in verts(c)) for c in hb), 2), "..",
      round(max(max(v[1] for v in verts(c)) for c in hb), 2))
print("hl_side  y range:", round(min(min(v[1] for v in verts(c)) for c in gn["hl_side"]["cubes"]), 2), "..",
      round(max(max(v[1] for v in verts(c)) for c in gn["hl_side"]["cubes"]), 2))
print("HairBack z range:", round(min(min(v[2] for v in verts(c)) for c in hb), 2), "..",
      round(max(max(v[2] for v in verts(c)) for c in hb), 2))
print("HairBack x range:", round(min(min(v[0] for v in verts(c)) for c in hb), 2), "..",
      round(max(max(v[0] for v in verts(c)) for c in hb), 2))
