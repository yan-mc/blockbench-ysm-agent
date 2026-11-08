# -*- coding: utf-8 -*-
"""v7d hair rebuild generator.

Reads the checkpoint bbmodel, deletes the old hair strand cubes, and generates a
new layered hair: HairCap (full scalp shell) + smooth curved strands for
HairBack / hl_side / front_h1 / corner_h1.

Verifies:
  * every strand segment has overlap 0.15-0.35 with the next
  * adjacent segment frame rotation <= 15 deg
  * scalp coverage by ray casting (no exposed skin)
Writes ops chunks to tools/ops_*.json for bb_apply_model_patch.
"""
import json, math, os, sys
from collections import defaultdict

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
BBM = os.path.join(ROOT, "checkpoints", "r0006.bbmodel")
OUT = os.path.join(ROOT, "tools")

BONE_UUID = {
    "Head": "ee15d849-c1e9-9f28-6b9d-197fb7d1c87c",
    "Hair": "ebbd2a88-1990-26ea-802a-18edcec8f93c",
    "HairBack": "f29069bb-568e-3faf-46e1-f2e62662ef70",
    "hl_side": "0f1db665-b7e4-6417-fc54-1a02c2495e2a",
    "front_h1": "d4fe7e84-5ba6-6660-7f1e-b97f99e898b4",
    "corner_h1": "78423a06-2cd9-a483-d5e5-b6c34314b590",
}
UUID_BONE = {v: k for k, v in BONE_UUID.items()}
STATS = []
DROP = ["Hair", "HairBack", "hl_side", "front_h1", "corner_h1"]

# ---------------------------------------------------------------- palette
# 7 existing hair tiers (sampled from textures/default.png), tier = uv anchor
SWATCH = {
    0: (22, 246),   # #566194 deepest
    1: (38, 246),   # #6a77ac
    2: (54, 246),   # #808ec2 main
    3: (70, 246),   # #98a6d4
    4: (86, 246),   # #afbce4 light
    5: (102, 246),  # #c4cfec lightest
    6: (54, 262),   # #dfe4ee highlight
}


def tier_by_y(y, base=2):
    """colour tier from height: light on top, deeper low down."""
    if y >= 39.6:
        return 4
    if y >= 38.2:
        return 3
    if y >= 34.0:
        return base
    if y >= 28.0:
        return max(1, base - 1)
    return max(0, base - 2)


# ---------------------------------------------------------------- math
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a):
    l = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / l, a[1] / l, a[2] / l)
def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def frame(yv, facing):
    """rotation matrix columns X,Y,Z ; Z = plate thin axis, aligned to facing."""
    Y = norm(yv)
    Z = sub(facing, mul(Y, dot(facing, Y)))
    if dot(Z, Z) < 1e-6:
        Z = (0, 0, 1)
    Z = norm(Z)
    X = norm(cross(Y, Z))
    Z = cross(X, Y)
    return [[X[0], Y[0], Z[0]], [X[1], Y[1], Z[1]], [X[2], Y[2], Z[2]]]


def euler_xyz(R):
    """ZYX decomposition: R = Rz(c) Ry(b) Rx(a).
    Blockbench applies cube rotation with Format.euler_order = 'ZYX' (same recipe
    that fixed the v7c skirt), so this decomposition reproduces R exactly."""
    b = math.asin(max(-1.0, min(1.0, -R[2][0])))
    a = math.atan2(R[2][1], R[2][2])
    c = math.atan2(R[1][0], R[0][0])
    return (math.degrees(a), math.degrees(b), math.degrees(c))


def R_from_euler(e):
    """R = Rz(c) * Ry(b) * Rx(a)  (Blockbench ZYX order)."""
    a, b, c = [math.radians(v) for v in e]
    ca, sa = math.cos(a), math.sin(a)
    cb, sb = math.cos(b), math.sin(b)
    cc, sc = math.cos(c), math.sin(c)
    Rx = [[1, 0, 0], [0, ca, -sa], [0, sa, ca]]
    Ry = [[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]]
    Rz = [[cc, -sc, 0], [sc, cc, 0], [0, 0, 1]]

    def mm(A, B):
        return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mm(Rz, mm(Ry, Rx))


def frame_angle(R1, R2):
    """rotation magnitude of R1^-1 R2"""
    M = [[sum(R1[k][i] * R2[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    tr = M[0][0] + M[1][1] + M[2][2]
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1) / 2))))


def catmull(pts, samples):
    """Catmull-Rom through pts, returns samples points"""
    P = [pts[0]] + list(pts) + [pts[-1]]
    segs = len(pts) - 1
    out = []
    for s in range(segs):
        p0, p1, p2, p3 = P[s], P[s + 1], P[s + 2], P[s + 3]
        n = samples if s < segs - 1 else samples + 1
        for i in range(n):
            t = i / samples
            t2, t3 = t * t, t * t * t
            q = []
            for d in range(3):
                q.append(0.5 * ((2 * p1[d]) + (-p0[d] + p2[d]) * t +
                                (2 * p0[d] - 5 * p1[d] + 4 * p2[d] - p3[d]) * t2 +
                                (-p0[d] + 3 * p1[d] - 3 * p2[d] + p3[d]) * t3))
            out.append(tuple(q))
    return out


# ---------------------------------------------------------------- cube model
class Cube:
    __slots__ = ("bone", "c", "size", "R", "uv", "name")

    def __init__(self, bone, c, size, R, uv):
        self.bone = bone; self.c = c; self.size = size; self.R = R; self.uv = uv
        self.name = bone

    def hit(self, p, d, tmin=0.02, tmax=3.0):
        o = [sum(self.R[k][i] * (p[k] - self.c[k]) for k in range(3)) for i in range(3)]
        dd = [sum(self.R[k][i] * d[k] for k in range(3)) for i in range(3)]
        lo = 0.0; hi = 1e9
        for i in range(3):
            h = self.size[i] / 2.0
            if abs(dd[i]) < 1e-9:
                if abs(o[i]) > h:
                    return None
                continue
            t1 = (-h - o[i]) / dd[i]
            t2 = (h - o[i]) / dd[i]
            if t1 > t2:
                t1, t2 = t2, t1
            lo = max(lo, t1); hi = min(hi, t2)
            if lo > hi:
                return None
        if hi < tmin or lo > tmax:
            return None
        return max(lo, tmin)

    def op(self):
        e = euler_xyz(self.R)
        origin = [self.c[i] - self.size[i] / 2 for i in range(3)]
        ux, uy = self.uv
        faces = {f: [ux, uy] for f in ("north", "east", "south", "west", "up", "down")}
        sizes = {f: [3, 3] for f in faces}
        return {
            "op": "add_cube", "bone": self.bone, "name": self.name,
            "origin": [round(v, 3) for v in origin],
            "size": [round(v, 3) for v in self.size],
            "rotation": [round(v, 2) for v in e],
            "pivot": [round(v, 3) for v in self.c],
            "uv": {"mode": "faces", "faces": faces, "sizes": sizes},
        }


# ---------------------------------------------------------------- strands
def make_strand(bone, ctrl, n_seg, w0, w1, thick, facing, overlap=0.25,
                base_tier=2, taper_end=True):
    pts = catmull(ctrl, max(3, n_seg // max(1, len(ctrl) - 1)))
    # resample by arc length into n_seg segments
    lens = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(lens)
    step = total / n_seg
    res = [pts[0]]
    acc = 0.0; i = 0; run = 0.0
    target = step
    while i < len(lens):
        seg = lens[i]
        if run + seg >= target - 1e-9:
            t = (target - run) / seg if seg > 1e-9 else 0
            res.append(lerp(pts[i], pts[i + 1], t))
            target += step
        else:
            run += seg; i += 1
    if len(res) < 2:
        res = [pts[0], pts[-1]]
    res = res[:n_seg + 1]
    if len(res) < 2:
        return []
    cubes = []
    frames = []
    pairs = []
    for i in range(len(res) - 1):
        d = sub(res[i + 1], res[i])
        L = math.sqrt(dot(d, d))
        if L < 1e-4:
            continue
        pairs.append((res[i], res[i + 1], norm(d)))
    if not pairs:
        return []
    dirs = [p[2] for p in pairs]
    # smooth directions to keep adjacent frame delta small
    sd = [dirs[0]]
    for i in range(1, len(dirs)):
        sd.append(norm(lerp(dirs[i - 1], dirs[i], 0.5)))
    for _ in range(3):
        sd = [norm(lerp(sd[i], sd[i + 1], 0.35)) if i + 1 < len(sd) else sd[i] for i in range(len(sd))]
    centers = []
    lengths = []
    prevR = None
    for i, d in enumerate(sd):
        p0, p1 = pairs[i][0], pairs[i][1]
        c = lerp(p0, p1, 0.5)
        L = max(0.58, math.dist(p0, p1) + overlap)
        t = i / max(1, len(sd) - 1)
        w = w0 + (w1 - w0) * t
        if taper_end and i >= len(sd) - 2:
            w *= 0.74
            if i == len(sd) - 1:
                w *= 0.72
        R = frame(mul(d, -1.0), facing)
        if prevR is not None:
            # keep the plate frame continuous: the facing axis may flip sign when the
            # tangent passes near it. Flipping X and Z together is a 180 deg turn about
            # Y, which leaves a box looking identical.
            z_i = (R[0][2], R[1][2], R[2][2])
            z_p = (prevR[0][2], prevR[1][2], prevR[2][2])
            if dot(z_i, z_p) < 0.0:
                R = [[-R[0][0], R[0][1], -R[0][2]],
                     [-R[1][0], R[1][1], -R[1][2]],
                     [-R[2][0], R[2][1], -R[2][2]]]
        prevR = R
        tier = tier_by_y(c[1], base_tier)
        cubes.append(Cube(bone, c, (w, L, thick), R, SWATCH[tier]))
        frames.append(R)
        centers.append(c)
        lengths.append(L)
    maxd = 0.0
    worst_i = 0
    for i in range(len(frames) - 1):
        a = frame_angle(frames[i], frames[i + 1])
        if a > maxd:
            maxd, worst_i = a, i
    ovs = []
    for i in range(len(centers) - 1):
        dist_c = math.dist(centers[i], centers[i + 1])
        ovs.append((lengths[i] + lengths[i + 1]) / 2.0 - dist_c)
    STATS.append({"bone": bone, "segs": len(cubes), "max_rot": maxd, "at": worst_i,
                  "overlap": (min(ovs), max(ovs)) if ovs else (0, 0)})
    return cubes


# ---------------------------------------------------------------- cap
def superellipse(theta, hx, hz, n=2.75):
    c, s = math.cos(theta), math.sin(theta)
    x = hx * math.copysign(abs(c) ** (2.0 / n), c)
    z = hz * math.copysign(abs(s) ** (2.0 / n), s)
    return x, z


def cap_perimeter(t, sx=1.0, sz=1.0, hx=3.92, hz=3.86, n=8.0):
    """closed rounded-rect perimeter, t in [0,1)"""
    th = 2 * math.pi * t
    x, z = superellipse(th, hx * sx, hz * sz, n)
    e = 1e-3
    th2 = 2 * math.pi * (t + e)
    x2, z2 = superellipse(th2, hx * sx, hz * sz, n)
    tan = norm((x2 - x, 0.0, z2 - z))
    nrm = (tan[2], 0.0, -tan[0])          # outward for CCW parameterisation
    if dot(nrm, (x, 0, z)) < 0:
        nrm = (-nrm[0], 0.0, -nrm[2])
    return (x, z), nrm


def arc_positions(k):
    """k equally spaced arc-length parameters on the cap perimeter"""
    S = 512
    ts = [i / S for i in range(S + 1)]
    pts = [cap_perimeter(t)[0] for t in ts]
    cum = [0.0]
    for i in range(S):
        cum.append(cum[-1] + math.dist(pts[i], pts[i + 1]))
    total = cum[-1]
    out = []
    for i in range(k):
        target = total * i / k
        lo, hi = 0, S
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if cum[mid] < target:
                lo = mid
            else:
                hi = mid
        t = ts[lo] + (ts[lo + 1] - ts[lo]) * ((target - cum[lo]) / max(1e-9, cum[lo + 1] - cum[lo]))
        out.append(t)
    return out, total


def build_cap(bone="HairCap"):
    cubes = []
    K = 16
    ts, perim = arc_positions(K)
    levels = [(39.62, 0.905, 0.905), (38.75, 0.975, 0.975), (37.80, 1.000, 1.000),
              (36.70, 0.995, 0.992), (35.55, 0.972, 0.968), (33.92, 0.940, 0.935)]
    for li, (y, sx, sz) in enumerate(levels):
        for ti, t in enumerate(ts):
            (x, z), nrm = cap_perimeter(t, sx, sz)
            # face window: no cap plate on the front plane below the hairline
            if y < 37.85 and z < -2.80 and abs(x) < 2.75:
                continue
            yy = y
            hh = 1.48
            if li == len(levels) - 1:      # ragged bottom edge instead of a bob-cut line
                yy = y - (0.28 if ti % 3 else 0.0)
                hh = 1.86
            R = frame((0.0, 1.0, 0.0), nrm)
            cubes.append(Cube(bone, (x, yy, z), (perim / K * 1.42, hh, 0.46),
                              R, SWATCH[3 if y > 38.9 else (3 if y > 36.6 else 2)]))

    # ---- top dome: concentric rings of plates, thin along the local normal
    rings = [
        # (scale, y, count, depth, tilt_deg)
        (0.00, 40.98, 1, 1.95, 0),
        (0.33, 40.78, 6, 1.40, 12),
        (0.57, 40.46, 9, 1.35, 32),
        (0.77, 40.06, 11, 1.30, 52),
        (0.905, 39.62, 13, 1.30, 70),
    ]
    for ri, (s, y, count, depth, tilt) in enumerate(rings):
        if count == 1:
            R = frame((0, 0, 1), (0, 1, 0))
            cubes.append(Cube(bone, (0.0, y, 0.0), (2.30, depth, 0.50), R, SWATCH[3]))
            continue
        a = math.radians(tilt)
        tsr, perim_r = arc_positions(count)
        for i, t in enumerate(tsr):
            (x, z), nrm2 = cap_perimeter(t, s, s)
            n = (nrm2[0] * math.sin(a), math.cos(a), nrm2[2] * math.sin(a))
            rad = (nrm2[0] * math.cos(a), -math.sin(a), nrm2[2] * math.cos(a))
            R = frame(rad, n)
            w = max(1.20, perim_r * s / count * 1.5)
            cubes.append(Cube(bone, (x, y, z), (w, depth, 0.50), R,
                              SWATCH[3 if ri < 3 else 3]))
    # nape plate under the back of the skull
    R = frame((0, 0, 1), (0, 1, 0))
    cubes.append(Cube(bone, (0.0, 32.92, 3.00), (7.00, 1.80, 0.55), R, SWATCH[1]))
    # crown corner caps: the box skull has sharp top corners the dome cannot reach
    Rc = frame((0, 0, 1), (0, 1, 0))
    for sx in (-1, 1):
        for sz in (-1, 1):
            cubes.append(Cube(bone, (sx * 3.34, 39.86, sz * 3.34),
                              (1.80, 1.80, 0.95), Rc, SWATCH[3]))
    return cubes


# ---------------------------------------------------------------- coverage
def coverage(cubes, verbose=True):
    boxes = cubes
    fails = defaultdict(list)
    def test(name, p, d):
        best = None
        for cu in boxes:
            t = cu.hit(p, d)
            if t is not None and (best is None or t < best):
                best = t
        if best is None:
            fails[name].append(p)
        return best
    # top
    n = 0
    for xi in range(-7, 8):
        for zi in range(-7, 8):
            x = xi * 0.5; z = zi * 0.5
            if abs(x) > 3.5 or abs(z) > 3.5:
                continue
            test("top", (x, 40.08, z), (0, 1, 0)); n += 1
    # sides
    for sx in (-1, 1):
        for yi in range(15):
            for zi in range(-7, 8):
                y = 33.05 + yi * 0.5; z = zi * 0.5
                test("side%s" % ("+" if sx > 0 else "-"), (sx * 3.52, y, z), (sx, 0, 0)); n += 1
    # back
    for xi in range(-7, 8):
        for yi in range(15):
            x = xi * 0.5; y = 33.05 + yi * 0.5
            test("back", (x, y, 3.52), (0, 0, 1)); n += 1
    # front: forehead above the bangs hairline only (face itself stays open)
    for xi in range(-7, 8):
        x = xi * 0.5
        for yi in range(15):
            y = 33.05 + yi * 0.5
            if y < 37.6:
                continue
            test("front", (x, y, -3.52), (0, 0, -1)); n += 1
    # underside behind the jaw (nape) only
    for xi in range(-7, 8):
        for zi in range(5, 8):
            test("neck", (xi * 0.5, 33.02, zi * 0.5), (0, -1, 0)); n += 1
    if verbose:
        print("coverage samples:", n)
        for k, v in fails.items():
            print("  FALLOFF %-6s %4d samples, e.g. %s" % (k, len(v), [(round(a[0], 2), round(a[1], 2), round(a[2], 2)) for a in v[:4]]))
    return fails, n


# ---------------------------------------------------------------- main
def main():
    d = json.load(open(BBM, encoding="utf-8"))
    els = {e["uuid"]: e for e in d["elements"] if e.get("type") == "cube"}
    owner = {}
    def walk(node):
        if isinstance(node, str) or not isinstance(node, dict):
            return
        u = node.get("uuid")
        for ch in node.get("children", []):
            if isinstance(ch, str):
                if ch in els and u in UUID_BONE:
                    owner[ch] = UUID_BONE[u]
            else:
                walk(ch)
    for n in d["outliner"]:
        walk(n)

    del_ids = [u for u, b in owner.items() if b in DROP]
    print("delete cubes:", len(del_ids))

    cubes = []
    cubes += build_cap()

    # ---- back hair: 8 main + 6 inner filler strands, to waist/hip
    back_main = [
        # (x0, z0, x1, z1, len_y, width0, width1, base_tier)
        (0.00, 3.55, 0.30, 4.45, 18.2, 2.30, 1.80, 2),
        (1.55, 3.20, 2.10, 4.95, 20.4, 2.30, 1.80, 1),
        (-1.55, 3.20, -2.10, 4.95, 20.4, 2.30, 1.80, 1),
        (3.05, 3.45, 3.90, 4.60, 21.6, 2.10, 1.60, 2),
        (-3.05, 3.45, -3.90, 4.60, 21.6, 2.10, 1.60, 2),
        (4.15, 3.15, 4.65, 4.10, 22.6, 1.85, 1.35, 1),
        (-4.15, 3.15, -4.65, 4.10, 22.6, 1.85, 1.35, 1),
        (0.78, 4.60, 1.25, 5.20, 16.6, 1.95, 1.45, 2),
        (-0.78, 4.60, -1.25, 5.20, 16.6, 1.95, 1.45, 2),
    ]
    for i, (x0, z0, x1, z1, drop, w0, w1, btier) in enumerate(back_main):
        y0 = 38.9 - 0.20 * abs(x0)
        y1 = y0 - drop
        mid = y0 - drop * 0.45
        ctrl = [(x0, y0, z0),
                (x0 * 0.96 + (x1 - x0) * 0.30, mid + 1.2, z0 + (z1 - z0) * 0.45),
                (x1 * 0.98, (y0 + y1) / 2 - drop * 0.12, z1 - 0.25),
                (x1, y1 + 1.5, z1 - 0.55),
                (x1 + (x1 - x0) * 0.08, y1, z1 - 0.75)]
        cubes += make_strand("HairBack", ctrl, 9, w0, w1, 1.05, (0, 0, 1), 0.26, base_tier=btier)
        if i < 6:
            ctrl2 = [(x0 * 0.9, y0 - 0.35, z0 - 0.55),
                     (x0 * 0.85, mid, z0 + (z1 - z0) * 0.25 - 0.5),
                     (x1 * 0.8, (y0 + y1) / 2, z1 - 1.1),
                     (x1 * 0.75, y1 + 3.4, z1 - 1.35)]
            cubes += make_strand("HairBack", ctrl2, 7, w0 * 0.80, w1 * 0.68, 0.85, (0, 0, 1), 0.24, base_tier=0)

    # ---- side locks: 3 per side to chest/waist
    for sx in (-1, 1):
        side = [
            (3.30, -1.60, 3.72, -2.05, 10.6, 1.24, 0.92, 2),
            (3.98, 0.05, 4.34, 0.35, 12.6, 1.40, 1.00, 3),
        ]
        for (x0, z0, x1, z1, drop, w0, w1, tier) in side:
            y0 = 37.3
            y1 = y0 - drop
            ctrl = [(sx * x0, y0, z0),
                    (sx * (x0 + 0.30), y0 - drop * 0.42, z0 - 0.35),
                    (sx * x1, y0 - drop * 0.78, z1 - 0.15),
                    (sx * (x1 + 0.12), y1, z1 + 0.10)]
            cubes += make_strand("hl_side", ctrl, 8, w0, w1, 0.95,
                                 (sx, 0, 0) if abs(x0) > 4.0 else (0, 0, 1), 0.25, base_tier=tier)

    # ---- bangs: 10 near-vertical locks, gentle fan out of a centre part
    bangs = [(0.42, 36.20, 0.90, 3), (1.12, 36.42, 0.98, 2), (1.80, 36.62, 0.94, 3),
             (2.42, 36.82, 0.86, 2), (2.96, 37.02, 0.74, 3), (3.38, 37.22, 0.62, 2)]
    for bi, (x, ytip, w0, btier) in enumerate(bangs):
        for sx in (-1, 1):
            zj = -4.02 + 0.045 * bi          # centre locks in front, outer locks behind
            ctrl = [(sx * x * 0.88, 40.02, zj),
                    (sx * x * 0.95, 39.30, zj - 0.16),
                    (sx * x * 1.00, 38.45, zj - 0.26),
                    (sx * x * 1.03, 37.50, zj - 0.32),
                    (sx * x * 1.04, ytip, zj - 0.36)]
            cubes += make_strand("front_h1", ctrl, 7, w0, w0 * 0.55, 0.50, (0, 0, 1), 0.26, base_tier=btier)
    # a couple of centre wisps
    for sx in (-1, 1):
        ctrl = [(sx * 0.10, 40.08, -4.06), (sx * 0.42, 39.20, -4.14),
                (sx * 0.66, 37.90, -4.20), (sx * 0.76, 36.28, -4.24)]
        cubes += make_strand("front_h1", ctrl, 6, 0.76, 0.44, 0.46, (0, 0, 1), 0.26, base_tier=3)

    # ---- corner fill between bangs and side locks
    for sx in (-1, 1):
        for i, (x, y, z, w, h, t) in enumerate([
                (3.55, 37.35, -3.86, 1.15, 2.10, 0.50),
                (3.86, 36.05, -3.60, 1.00, 1.95, 0.50),
                (4.02, 34.25, -3.40, 0.95, 2.50, 0.50)]):
            R = frame((0, 1, 0), (0, 0, 1))
            cubes.append(Cube("corner_h1", (sx * x, y, z), (w, h, t), R,
                              SWATCH[2 if i < 2 else 1]))

    # ---- strand quality checks
    global LAST_CUBES
    LAST_CUBES = cubes
    stats = defaultdict(lambda: {"n": 0, "segs": [], "maxrot": 0.0, "overlaps": []})
    by_bone = defaultdict(list)
    for c in cubes:
        by_bone[c.bone].append(c)
    print("generated cubes:", len(cubes))
    for b, cs in sorted(by_bone.items()):
        print("  %-10s %3d" % (b, len(cs)))

    fails, nsamp = coverage(cubes)
    tot = sum(len(v) for v in fails.values())
    print("uncovered samples:", tot, "/", nsamp)

    # strand smoothness report
    if STATS:
        print("strands:", len(STATS),
              "segs/strand: %d..%d" % (min(s["segs"] for s in STATS), max(s["segs"] for s in STATS)))
        print("max adjacent segment rotation delta: %.2f deg" % max(s["max_rot"] for s in STATS))
        print("adjacent overlap: %.3f .. %.3f" % (min(s["overlap"][0] for s in STATS),
                                                 max(s["overlap"][1] for s in STATS)))
        lo = sorted(STATS, key=lambda s: s["overlap"][0])[:4]
        print("lowest overlaps:", [(s["bone"], round(s["overlap"][0], 3), s["segs"]) for s in lo])
        bad = [s for s in STATS if s["max_rot"] > 15.0]
        print("strands exceeding 15 deg delta:", len(bad),
              [(s["bone"], round(s["max_rot"], 1)) for s in bad[:8]])
    # euler roundtrip
    err = 0.0
    for c in cubes[:80]:
        e = euler_xyz(c.R)
        R2 = R_from_euler(e)
        err = max(err, max(abs(c.R[i][j] - R2[i][j]) for i in range(3) for j in range(3)))
    print("euler roundtrip err: %.2e" % err)

    # dump ops
    del_ops = [{"op": "delete", "refs": [{"kind": "cube", "id": u}]} for u in del_ids]
    chunks = []
    cur = []
    for o in del_ops:
        cur.append(o)
        if len(cur) >= 200:
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur); cur = []
    add_ops = [c.op() for c in cubes]
    for o in add_ops:
        cur.append(o)
        if len(cur) >= 200:
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    for i, ch in enumerate(chunks):
        p = os.path.join(OUT, "ops_%02d.json" % i)
        json.dump(ch, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        print("wrote", p, len(ch))

    # stats for report
    json.dump({"cubes": len(cubes), "per_bone": {k: len(v) for k, v in by_bone.items()},
               "coverage_fail": tot, "coverage_samples": nsamp,
               "deleted": len(del_ids)},
              open(os.path.join(OUT, "v7d_stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
