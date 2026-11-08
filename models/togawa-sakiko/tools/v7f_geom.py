import json, os, math
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
P = os.path.join(BASE, "pack", "models", "main.json")
R = math.radians

def rotM(rot):
    a, b, c = (rot or [0, 0, 0]); a, b, c = R(a), R(b), R(c)
    ca, sa = math.cos(a), math.sin(a); cb, sb = math.cos(b), math.sin(b); cc, sc = math.cos(c), math.sin(c)
    return [[cb*cc, -cb*sc, sb],
            [ca*sc + sa*sb*cc, ca*cc - sa*sb*sc, -sa*cb],
            [sa*sc - ca*sb*cc, sa*cc + ca*sb*sc, ca*cb]]

def verts(c):
    o = c["origin"]; s = c["size"]; M = rotM(c.get("rotation"))
    cen = [o[i] + s[i]/2 for i in range(3)]
    out = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                p = [sx*s[0]/2, sy*s[1]/2, sz*s[2]/2]
                out.append([sum(M[i][j]*p[j] for j in range(3)) + cen[i] for i in range(3)])
    return out

def top_at(c, x, z):
    """exact: highest y of oriented box at (x,z); None if no hit"""
    o = c["origin"]; s = c["size"]; M = rotM(c.get("rotation"))
    cen = [o[i] + s[i]/2 for i in range(3)]
    # local ray: o' = R^T (p - cen), d' = R^T (0,-1,0)
    d = [M[1][0]*0 + M[1][1]*(-1) + M[1][2]*0, 0, 0]  # placeholder
    # R^T * (0,-1,0) = -(row? ) -> R^T column: (R^T * e_y) = row1 of R? compute properly
    dl = [-M[0][1], -M[1][1], -M[2][1]]
    pl = [M[0][0]*(x-cen[0]) + M[1][0]*(100-cen[1]) + M[2][0]*(z-cen[2]),
          M[0][1]*(x-cen[0]) + M[1][1]*(100-cen[1]) + M[2][1]*(z-cen[2]),
          M[0][2]*(x-cen[0]) + M[1][2]*(100-cen[1]) + M[2][2]*(z-cen[2])]
    tmin, tmax = -1e9, 1e9
    for i in range(3):
        h = s[i]/2.0
        if abs(dl[i]) < 1e-9:
            if abs(pl[i]) > h: return None
        else:
            t1 = (-h - pl[i])/dl[i]; t2 = (h - pl[i])/dl[i]
            if t1 > t2: t1, t2 = t2, t1
            tmin = max(tmin, t1); tmax = min(tmax, t2)
            if tmin > tmax: return None
    if tmax < 0: return None
    return 100 + tmax*dl[1] + 0  # y = 100 + t*dl_y (dl_y = -1 always? no)

def ray_hit(c, x, z):
    """returns highest y where the ray (x,100,z)->-Y enters/exit box"""
    o = c["origin"]; s = c["size"]; M = rotM(c.get("rotation"))
    cen = [o[i] + s[i]/2 for i in range(3)]
    d = [0.0, -1.0, 0.0]
    # local
    px = [x-cen[0], 100-cen[1], z-cen[2]]
    pl = [sum(M[i][0]*px[i] for i in range(3)), sum(M[i][1]*px[i] for i in range(3)), sum(M[i][2]*px[i] for i in range(3))]
    dl = [sum(M[i][0]*d[i] for i in range(3)), sum(M[i][1]*d[i] for i in range(3)), sum(M[i][2]*d[i] for i in range(3))]
    tmin, tmax = -1e9, 1e9
    for i in range(3):
        h = s[i]/2.0
        if abs(dl[i]) < 1e-9:
            if abs(pl[i]) > h: return None
        else:
            t1 = (-h - pl[i])/dl[i]; t2 = (h - pl[i])/dl[i]
            if t1 > t2: t1, t2 = t2, t1
            tmin = max(tmin, t1); tmax = min(tmax, t2)
            if tmin > tmax: return None
    if tmax < 0: return None
    return 100 + tmax*d[1]

d = json.load(open(P, encoding="utf-8"))
G = d["minecraft:geometry"][0]
bc = {b["name"]: b for b in G["bones"]}
hair_bones = [n for n in bc if bc[n].get("parent") in ("Hair", "LongHair") or n.startswith("Hair") or n.startswith("hl_") or n.startswith("corner") or n.startswith("Twin")]
print("hair-ish bones:", sorted(set(hair_bones)))
# gather ALL cubes of HairCap + front_h1 (for crown surface)
cap = bc["HairCap"]["cubes"]
grid = 0.2
xs = [(-3.4 + i*grid) for i in range(int(6.8/grid)+1)]
zs = [(-3.4 + i*grid) for i in range(int(6.8/grid)+1)]
h = {}
holes = 0; lowest = 99
for x in xs:
    for z in zs:
        if math.hypot(x, z) > 3.4: continue
        best = None
        for c in cap:
            t = ray_hit(c, x, z)
            if t is not None and (best is None or t > best): best = t
        h[(round(x, 2), round(z, 2))] = best
        if best is None or best < 40.3:
            holes += 1; lowest = min(lowest, best if best is not None else 0)
print(f"r<=3.4 cells={len(h)} holes(<40.3)={holes} lowest={lowest}")
vals = [v for v in h.values() if v]
print(f"height: min={min(vals):.2f} max={max(vals):.2f}")
# local step: adjacent 0.2 cells
steps = []
for (x, z), v in h.items():
    if v is None: continue
    for dx, dz in ((grid, 0), (0, grid)):
        w = h.get((round(x+dx, 2), round(z+dz, 2)))
        if w is not None: steps.append(abs(v-w))
steps.sort()
print(f"steps: n={len(steps)} max={steps[-1]:.2f} p99={steps[int(len(steps)*0.99)]:.2f} p95={steps[int(len(steps)*0.95)]:.2f} >0.25: {sum(1 for s in steps if s>0.25)}")

# support function (top-view convex silhouette) over all hair bones
allc = []
for n in ("HairCap", "front_h1", "corner_h1"):
    allc += bc[n]["cubes"]
pts = []
for c in allc:
    for v in verts(c): pts.append((v[0], v[2]))
print("\n### top-view support radius r(theta): current")
rows = []
for k in range(72):
    th = R(360.0*k/72); ca, sa = math.cos(th), math.sin(th)
    r = max(x*ca + z*sa for x, z in pts)
    rows.append(r)
print("min", round(min(rows), 2), "max", round(max(rows), 2), "max/min", round(max(rows)/min(rows), 3))
# jaggedness: max |r(k+1)-r(k)| in units (2.5 deg step => arc length)
difs = [abs(rows[(k+1) % 72]-rows[k]) for k in range(72)]
print("jag max step per 5deg:", round(max(difs), 2), "mean", round(sum(difs)/len(difs), 2))
print(" ".join(f"{k*5}:{rows[k]:.1f}" for k in range(0, 72, 4)))
