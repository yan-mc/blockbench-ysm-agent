import json, math, sys, statistics

P = sys.argv[1] if len(sys.argv) > 1 else r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
d = json.load(open(P, encoding="utf-8"))
g = d["minecraft:geometry"][0]
bones = g["bones"]
by = {b["name"]: b for b in bones}
SK = ["Skirt", "RightSkirt", "LeftSkirt", "FrontSkirt", "BackSkirt"]


def mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def rx(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def ry(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def R_of(rot):
    a, b, c = [math.radians(v) for v in rot]
    return mm(mm(rz(c), ry(b)), rx(a))  # ZYX


def cube_corners(c, off):
    o = c["origin"]; s = c["size"]
    p = c.get("pivot", [o[0] + s[0] / 2, o[1] + s[1] / 2, o[2] + s[2] / 2])
    R = R_of(c.get("rotation", [0, 0, 0]))
    pts = []
    for dx in (0, s[0]):
        for dy in (0, s[1]):
            for dz in (0, s[2]):
                v = [o[0] + dx - p[0], o[1] + dy - p[1], o[2] + dz - p[2]]
                w = [sum(R[i][j] * v[j] for j in range(3)) + p[i] + off[i] for i in range(3)]
                pts.append(w)
    return pts


def stats(names, off=(0, 0, 0), label=""):
    allp = []
    per = {}
    for b in bones:
        if b["name"] not in names:
            continue
        ps = []
        for c in b.get("cubes", []):
            ps += cube_corners(c, off)
        per[b["name"]] = ps
        allp += ps
    lo = [min(p[i] for p in allp) for i in range(3)]
    hi = [max(p[i] for p in allp) for i in range(3)]
    print(f"{label} n={len(allp)//8} bbox x {lo[0]:.2f}..{hi[0]:.2f} (c {(lo[0]+hi[0])/2:.2f}) y {lo[1]:.2f}..{hi[1]:.2f} z {lo[2]:.2f}..{hi[2]:.2f} (c {(lo[2]+hi[2])/2:.2f})")
    for n, ps in per.items():
        if not ps:
            continue
        l = [min(p[i] for p in ps) for i in range(3)]
        h = [max(p[i] for p in ps) for i in range(3)]
        m = [statistics.mean(p[i] for p in ps) for i in range(3)]
        print(f"   {n:<12} n={len(ps)//8:<3} x {l[0]:6.2f}..{h[0]:6.2f} c {(l[0]+h[0])/2:6.2f} | y {l[1]:6.2f}..{h[1]:6.2f} | z {l[2]:6.2f}..{h[2]:6.2f} c {(l[2]+h[2])/2:6.2f} | mean {m[0]:6.2f},{m[1]:6.2f},{m[2]:6.2f}")
    return allp


print("desc", json.dumps(g["description"], ensure_ascii=False))
print("bones", len(bones), "cubes", sum(len(b.get("cubes", [])) for b in bones))
print("names:", ", ".join(b["name"] for b in bones))
print()
print("--- no bone offset ---")
stats(set(SK), (0, 0, 0), "SKIRT")
print()
for nm in ["UpperBody", "AllHead", "Head", "LeftLeg", "RightLeg", "Body", "DownBody", "UpBody"]:
    if nm in by:
        stats({nm}, (0, 0, 0), nm)

# hem / top profile with no offset
p_all = []
for b in bones:
    if b["name"] not in SK:
        continue
    for c in b.get("cubes", []):
        p_all.append(cube_corners(c, (0, 0, 0)))
print("\n--- hem/top by azimuth (front=-z, side=+/-x, back=+z) ---")
for k in range(16):
    phi = -math.pi + 2 * math.pi * k / 16
    sel = []
    for ps in p_all:
        ctr = [sum(p[i] for p in ps) / 8 for i in range(3)]
        ang = math.atan2(ctr[0], -ctr[2])
        da = abs((ang - phi + math.pi) % (2 * math.pi) - math.pi)
        if da < 2 * math.pi / 16 / 2:
            sel += ps
    if not sel:
        continue
    ys = [p[1] for p in sel]
    rr = [math.hypot(p[0], p[2]) for p in sel]
    print(f"  phi={math.degrees(phi):7.1f} ymin {min(ys):6.2f} ymax {max(ys):6.2f} r {min(rr):5.2f}..{max(rr):5.2f}")

# check per-bone offsets: if cubes were bone-local, add bone pivot
print("\n--- WITH bone pivot offset (local-space hypothesis) ---")
for b in bones:
    if b["name"] not in SK:
        continue
    piv = b.get("pivot", [0, 0, 0])
    stats({b["name"]}, tuple(piv), "  " + b["name"])
