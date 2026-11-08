"""v7c skirt rebuild: v6.2 plate recipe + continuous slanted hem (front 15.5 / side 14.0 / back 12.5)."""
import json, math, os, sys

BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
MAIN = os.path.join(BASE, "pack", "models", "main.json")
OUT = os.path.join(BASE, "artifacts", "v7c")
os.makedirs(OUT, exist_ok=True)
WRITE = "--write" in sys.argv

# editor space: front = -Z, +X = character right, +Y up. Euler order ZYX (v6.2 recipe).
def mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

def rx(a):
    c, s = math.cos(a), math.sin(a); return [[1, 0, 0], [0, c, -s], [0, s, c]]

def ry(a):
    c, s = math.cos(a), math.sin(a); return [[c, 0, s], [0, 1, 0], [-s, 0, c]]

def rz(a):
    c, s = math.cos(a), math.sin(a); return [[c, -s, 0], [s, c, 0], [0, 0, 1]]

def euler_zyx_deg(R):
    """ZYX decomposition (Blockbench Format.euler_order = 'ZYX'): R = Rz(c) Ry(b) Rx(a)."""
    b = math.asin(max(-1.0, min(1.0, -R[2][0])))
    cb = math.cos(b)
    if abs(cb) > 1e-6:
        a = math.atan2(R[2][1], R[2][2]); c = math.atan2(R[1][0], R[0][0])
    else:
        c = 0.0
        a = math.atan2(-R[1][2], R[1][1]) if b > 0 else math.atan2(R[1][2], R[1][1])
    return [math.degrees(a), math.degrees(b), math.degrees(c)]

def recompose(eul):
    a, b, c = [math.radians(v) for v in eul]
    return mm(mm(rz(c), ry(b)), rx(a))

def norm(v):
    l = math.sqrt(sum(x * x for x in v)); return [x / l for x in v]

def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]

BONES = [
    ("Skirt", "DownBody", [0, 23.85, 0.1]),
    ("RightSkirt", "Skirt", [3.525, 23.9, 0.0375]),   # character right = +X
    ("LeftSkirt", "Skirt", [-3.6, 23.9, 0.0375]),
    ("FrontSkirt", "Skirt", [0, 24.25, -2.0125]),
    ("BackSkirt", "Skirt", [0, 24.1, 2.4125]),
]

def bone_for_angle(deg):
    a = deg % 360.0
    if a < 60.0 or a >= 300.0:
        return "FrontSkirt"
    if a < 120.0:
        return "RightSkirt"
    if a < 240.0:
        return "BackSkirt"
    return "LeftSkirt"

Y_TOP_ANCHOR = 22.80   # shift = 0 at/above this
Y_HEM0 = 13.00         # shift full at hem
BASE_SHIFT = 1.00
AMP = 1.50             # front +2.5, side +1.0, back -0.5 at hem

def slant(th_deg, y):
    u = (Y_TOP_ANCHOR - y) / (Y_TOP_ANCHOR - Y_HEM0)
    u = max(0.0, min(1.0, u))
    return (BASE_SHIFT + AMP * math.cos(math.radians(th_deg))) * u

def notch(th_deg):
    d = (th_deg + 180.0) % 360.0 - 180.0
    if abs(d) >= 12.0:
        return 0.0
    return 0.30 * (1.0 - abs(d) / 12.0)

BLACK_MID = [200, 18]
BLACK_DARK = [226, 18]
BLACK_HI = [258, 18]
BLUE_ROYAL = [100, 230]
BLUE_MID = [116, 230]
BLUE_LIGHT = [132, 230]
WHITE_HI = [164, 230]
WHITE_LO = [150, 230]

def panel_ops(n, y_top, y_bot, r_top, r_bot, thick, phase, overlap, uv_off, name,
              z_ratio=0.96, bone_override=None, pitch_extra=0.0, width_n=None,
              roll_deg=0.0, use_slant=True, use_notch=False):
    ops = []
    r_mid = 0.5 * (r_top + r_bot)
    circ = 2 * math.pi * r_mid * (0.5 * (1 + z_ratio))
    w = circ / (width_n or n) * overlap
    for i in range(n):
        th_deg = phase + i * 360.0 / n
        th = math.radians(th_deg)
        st = slant(th_deg, y_top) if use_slant else 0.0
        sb = slant(th_deg, y_bot) if use_slant else 0.0
        nt = notch(th_deg) if use_notch else 0.0
        y_t = y_top + st + nt
        y_b = y_bot + sb + nt
        s, c = math.sin(th), math.cos(th)
        pt = [r_top * s, y_t, -r_top * z_ratio * c]
        nrm = norm([s / r_top, 0.0, -c / (r_top * z_ratio)])
        tan = norm(cross([0, 1, 0], nrm))
        dr = r_bot - r_top
        dy = y_b - y_t
        d = norm([nrm[0] * dr, dy, nrm[2] * dr])
        h = math.hypot(dr, dy)
        if pitch_extra:
            ang = math.radians(pitch_extra)
            ca, sa = math.cos(ang), math.sin(ang)
            axis = tan
            ad = sum(axis[k] * d[k] for k in range(3))
            axd = cross(axis, d)
            d = norm([d[k] * ca + axd[k] * sa + axis[k] * ad * (1 - ca) for k in range(3)])
        zax = norm(cross(tan, d))
        R = [[tan[0], d[0], zax[0]], [tan[1], d[1], zax[1]], [tan[2], d[2], zax[2]]]
        if roll_deg:
            rr = math.radians(roll_deg if i % 2 == 0 else -roll_deg)
            R = mm(R, rz(rr))
        eul = euler_zyx_deg(R)
        R2 = recompose(eul)
        ERRORS.append(max(abs(R[i][j] - R2[i][j]) for i in range(3) for j in range(3)))
        pivot = [pt[0] + nrm[0] * thick * 0.5, pt[1] + nrm[1] * thick * 0.5, pt[2] + nrm[2] * thick * 0.5]
        loc = [w * 0.5, 0.0, thick * 0.5]
        # origin is the UNrotated min corner relative to the pivot: pivot - [w/2, 0, t/2]
        # (v6.2 recipe wrongly applied R a second time here, displacing every plate)
        wx = [pivot[k] - loc[k] for k in range(3)]
        bone = bone_override or bone_for_angle(th_deg)
        ops.append({
            "op": "add_cube", "bone": bone, "name": name,
            "origin": [round(v, 4) for v in wx],
            "size": [round(w, 4), round(h, 4), round(thick, 4)],
            "pivot": [round(v, 4) for v in pivot],
            "rotation": [round(v, 4) for v in eul],
            "uv": [uv_off[0], uv_off[1]],
        })
    return ops

ops = []
ERRORS = []
# 1 waistband (12) - flat, flush on body
ops += panel_ops(12, 23.60, 22.55, 3.00, 3.08, 0.32, 5.0, 1.20, BLACK_MID, "SkirtWaist",
                 bone_override="Skirt", roll_deg=1.5, use_slant=False)
# 2 inner waistband (12) - dark, hugs corset
ops += panel_ops(12, 24.10, 22.40, 2.78, 2.88, 0.26, 11.0, 1.25, BLACK_DARK, "SkirtWaistInner",
                 bone_override="Skirt", roll_deg=1.2, use_slant=False)
# 3-5 black tiers (16 each)
ops += panel_ops(16, 23.15, 19.55, 3.00, 4.15, 0.30, 7.0, 1.32, BLACK_MID, "SkirtTierA",
                 roll_deg=2.2, use_notch=True)
ops += panel_ops(16, 19.75, 17.25, 4.32, 5.30, 0.32, 3.0, 1.25, BLACK_MID, "SkirtTierB",
                 roll_deg=2.2, use_notch=True)
ops += panel_ops(16, 17.45, 15.45, 5.45, 6.15, 0.34, 11.0, 1.25, BLACK_MID, "SkirtTierC",
                 roll_deg=2.2, use_notch=True)
# 6 upper flounce (30) - T3 peplum layer
ops += panel_ops(30, 17.70, 16.60, 5.85, 6.28, 0.30, 1.5, 1.38, BLACK_MID, "SkirtRuffle2",
                 pitch_extra=2.5, roll_deg=1.8, use_notch=True)
# 7 hem ruffle (30)
ops += panel_ops(30, 16.55, 15.30, 6.08, 6.50, 0.34, 6.0, 1.38, BLACK_HI, "SkirtRuffleHem",
                 pitch_extra=3.0, roll_deg=1.8, use_notch=True)
# 8 continuous dark inner shell (36) waist -> hem, strong overlap
ops += panel_ops(36, 23.20, 13.00, 2.75, 6.45, 0.24, 4.5, 1.60, BLACK_DARK, "SkirtInnerShell",
                 roll_deg=1.4)
# 9 blue underskirt (36) striped
blue_uvs = [BLUE_MID, BLUE_ROYAL, BLUE_LIGHT, BLUE_MID, BLUE_ROYAL, BLUE_MID]
for idx in range(36):
    ops += panel_ops(1, 15.90, 13.35, 6.02, 6.84, 0.30, 8.0 + idx * 10.0, 1.50, blue_uvs[idx % 6],
                     "SkirtBlue", bone_override=bone_for_angle(8.0 + idx * 10.0), width_n=36, roll_deg=1.8)
# 10 white trim (40)
for idx in range(40):
    uv = WHITE_LO if idx % 5 == 0 else WHITE_HI
    ops += panel_ops(1, 13.35, 13.00, 6.88, 7.00, 0.30, 2.0 + idx * 9.0, 1.70, uv,
                     "SkirtWhiteTrim", bone_override=bone_for_angle(2.0 + idx * 9.0), width_n=40, roll_deg=1.6)
print("euler reconstruction max err = %.2e" % max(ERRORS))

# ---------------- audit (design space) ----------------
def obb(o):
    """corner set of a generated plate (editor space, exact by construction)"""
    return o["_corners"]

# rebuild corners from ops: we know origin/size/pivot/rotation; use ZYX (design convention)
def corners_of(o):
    ox, oy, oz = o["origin"]; sx, sy, sz = o["size"]; p = o["pivot"]
    a, b, c = [math.radians(v) for v in o["rotation"]]
    R = mm(mm(rz(c), ry(b)), rx(a))
    pts = []
    for dx in (0, sx):
        for dy in (0, sy):
            for dz in (0, sz):
                v = [ox + dx - p[0], oy + dy - p[1], oz + dz - p[2]]
                pts.append([sum(R[i][j] * v[j] for j in range(3)) + p[i] for i in range(3)])
    return pts

allp = []
for o in ops:
    allp += corners_of(o)
lo = [min(p[i] for p in allp) for i in range(3)]
hi = [max(p[i] for p in allp) for i in range(3)]
print("NEW SKIRT cubes", len(ops))
print("bbox x %.2f..%.2f c %.2f | y %.2f..%.2f | z %.2f..%.2f c %.2f" % (
    lo[0], hi[0], (lo[0] + hi[0]) / 2, lo[1], hi[1], lo[2], hi[2], (lo[2] + hi[2]) / 2))
print("counts by bone", {b: sum(1 for o in ops if o["bone"] == b) for b in ["Skirt", "RightSkirt", "LeftSkirt", "FrontSkirt", "BackSkirt"]})
tri = sum(1 for o in ops if all(abs(v) > 1e-9 for v in o["rotation"]))
print("tri-axis %d/%d = %.1f%%" % (tri, len(ops), 100.0 * tri / len(ops)))
for nm, th in (("front", 0), ("right", 90), ("back", 180), ("left", 270)):
    print("hem %-5s y = %.2f" % (nm, 13.00 + slant(th, 13.00)))
print("top ring y (waist) = %.2f..%.2f" % (22.55, 23.60))

# occlusion: rays toward thigh boxes must hit a skirt plate first
def make_test(o):
    pts = corners_of(o)
    ctr = [sum(p[i] for p in pts) / 8 for i in range(3)]
    sx, sy, sz = o["size"]
    a, b, c = [math.radians(v) for v in o["rotation"]]
    R = mm(mm(rz(c), ry(b)), rx(a))
    return (ctr, R, [sx / 2, sy / 2, sz / 2])

plates = [make_test(o) for o in ops]

def hit(box, p, dv):
    ctr, R, h = box
    o = [p[i] - ctr[i] for i in range(3)]
    lo_ = [sum(R[i][j] * o[i] for i in range(3)) for j in range(3)]
    ld = [sum(R[i][j] * dv[i] for i in range(3)) for j in range(3)]
    tmin, tmax = -1e18, 1e18
    for i in range(3):
        if abs(ld[i]) < 1e-9:
            if abs(lo_[i]) > h[i] or abs(lo_[i]) > h[i]:
                if abs(lo_[i]) > h[i]:
                    return None
        else:
            t1 = (-h[i] - lo_[i]) / ld[i]; t2 = (h[i] - lo_[i]) / ld[i]
            if t1 > t2:
                t1, t2 = t2, t1
            tmin = max(tmin, t1); tmax = min(tmax, t2)
    if tmax < max(tmin, 0):
        return None
    return max(tmin, 0.0)

def nearest(p, dv):
    best = None
    for b in plates:
        t = hit(b, p, dv)
        if t is not None and (best is None or t < best):
            best = t
    return best

legs = []
for sx in (-2.35, 2.35):
    for yy in (15.0, 17.4, 19.8):
        legs.append(([sx, yy, 0.0], [[1, 0, 0], [0, 1, 0], [0, 0, 1]], [1.05, 1.30, 1.05]))

tot = blk = 0
miss = []
for k in range(72):
    phi = 2 * math.pi * k / 72
    th_deg = math.degrees(phi)
    hem = 13.00 + slant(th_deg, 13.00)
    yy = hem + 0.35
    while yy < 21.4:
        p = [12.0 * math.sin(phi), yy, -12.0 * math.cos(phi)]
        dv = [-math.sin(phi), 0.0, math.cos(phi)]
        tl = None
        for l in legs:
            t = hit(l, p, dv)
            if t is not None and (tl is None or t < tl):
                tl = t
        if tl is not None:
            tot += 1
            ts = nearest(p, dv)
            if ts is not None and ts < tl:
                blk += 1
            else:
                miss.append((round(th_deg), round(yy, 1)))
        yy += 0.5
print("thigh occlusion (rays above local hem): %d/%d = %.1f%%" % (blk, tot, 100.0 * blk / max(tot, 1)))
if miss:
    print("  missed rays:", miss[:12])
# radial shell coverage: no gap straight through to the axis
tot2 = cov2 = 0
for k in range(72):
    phi = 2 * math.pi * k / 72
    th_deg = math.degrees(phi)
    hem = 13.00 + slant(th_deg, 13.00)
    yy = hem + 0.30
    while yy < 23.2:
        p = [12.0 * math.sin(phi), yy, -12.0 * math.cos(phi)]
        dv = [-math.sin(phi), 0.0, math.cos(phi)]
        tot2 += 1
        if nearest(p, dv) is not None:
            cov2 += 1
        yy += 0.4
print("radial shell coverage: %d/%d = %.1f%%" % (cov2, tot2, 100.0 * cov2 / max(tot2, 1)))

# ---------------- write main.json ----------------
if WRITE:
    doc = json.load(open(MAIN, encoding="utf-8"))
    geo = doc["minecraft:geometry"][0]
    bones = geo["bones"]
    new_bones = []
    for nm, par, piv in BONES:
        new_bones.append({"name": nm, "parent": par, "pivot": piv, "cubes": []})

    def conv(o):
        x, y, z = o["origin"]; w_, h_, t_ = o["size"]; px, py, pz = o["pivot"]
        ax, ay, az = o["rotation"]
        return {"origin": [round(-(x + w_), 4), round(y, 4), round(z, 4)],
                "size": [round(w_, 4), round(h_, 4), round(t_, 4)],
                "pivot": [round(-px, 4), round(py, 4), round(pz, 4)],
                "rotation": [round(-ax, 4), round(-ay, 4), round(az, 4)],
                "uv": [o["uv"][0], o["uv"][1]]}

    for b in new_bones:
        b["cubes"] = [conv(o) for o in ops if o["bone"] == b["name"]]

    old = ["Skirt", "RightSkirt", "LeftSkirt", "FrontSkirt", "BackSkirt"]
    removed = sum(len(b.get("cubes", [])) for b in bones if b["name"] in old)
    idx = next(i for i, b in enumerate(bones) if b["name"] == "Skirt")
    kept = [b for b in bones if b["name"] not in old]
    bones[:] = kept[:idx] + new_bones + kept[idx:]
    geo["bones"] = bones
    with open(MAIN, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent="\t")
        f.write("\n")
    tot_cubes = sum(len(b.get("cubes", [])) for b in bones)
    print("removed", removed, "added", len(ops), "total cubes", tot_cubes, "bones", len(bones))
    json.dump(ops, open(os.path.join(OUT, "skirt_ops.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
else:
    print("(dry run, not written)")
