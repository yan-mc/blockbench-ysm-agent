"""v7a skirt rebuild: world-coord truncated cone, slanted hem, tilted thin plates.

Editor space (Blockbench): +x = character LEFT, -z = FRONT, +y = up.
main.json (YSM/Bedrock export) stores a mirrored x and negated rx/ry:
    json.origin = [-(ex+sx), ey, ez]      json.rotation = [-rx, -ry, rz]
    json.pivot  = [-px, py, pz]
(verified on 3 real cubes against bb_get_element)
"""
import json, math, shutil, sys

P = r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json'

# ---------------- palette (texture 512 default.png) ----------------
UV = {
    'black_mid':   (200, 18),   # #262230
    'black_dark':  (226, 18),   # #17151c
    'black_light': (258, 18),   # #332f3a
    'near_black':  (230, 40),   # #211e27
    'near_black2': (270, 40),   # #1b1920
    'blue_deep':   (100, 230),  # #2c4ea9
    'blue_mid':    (116, 230),  # #3f6bb5
    'blue_light':  (132, 230),  # #6f9ad0
    'blue_pale':   (150, 230),  # #cfe0f5
    'blue_white':  (164, 230),  # #e4eefb
}

CX, CZ = -0.15, 0.0
BODY_CX = 0.0     # measured hip block centre (x +-2.9, symmetric)


def se_r(a_deg, rx, rz, n):
    """superellipse radius at azimuth a (0 = front, +90 = +x)."""
    a = math.radians(a_deg)
    s, c = abs(math.sin(a)), abs(math.cos(a))
    return ((s / rx) ** n + (c / rz) ** n) ** (-1.0 / n)


def mat_mul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def basis(a_deg, phi):
    """plate basis: X = tangent, Y = up-inward, Z = X x Y."""
    a = math.radians(a_deg)
    u = (math.sin(a), 0.0, -math.cos(a))
    t = (math.cos(a), 0.0, math.sin(a))
    Y = (-math.sin(phi) * u[0], math.cos(phi), -math.sin(phi) * u[2])
    Z = (t[1] * Y[2] - t[2] * Y[1], t[2] * Y[0] - t[0] * Y[2], t[0] * Y[1] - t[1] * Y[0])
    return t, Y, Z


def euler_xyz(R):
    """R = Rx(a)Ry(b)Rz(c)  ->  (a,b,c) degrees."""
    b = math.asin(max(-1.0, min(1.0, R[0][2])))
    a = math.atan2(-R[1][2], R[2][2])
    c = math.atan2(-R[0][1], R[0][0])
    return math.degrees(a), math.degrees(b), math.degrees(c)


def rebuild_rot(R):
    a, b, c = (math.radians(v) for v in euler_xyz(R))
    ca, sa = math.cos(a), math.sin(a)
    cb, sb = math.cos(b), math.sin(b)
    cc, sc = math.cos(c), math.sin(c)
    return [[cb * cc, -cb * sc, sb],
            [sa * sb * cc + ca * sc, -sa * sb * sc + ca * cc, -sa * cb],
            [-ca * sb * cc + sa * sc, ca * sb * sc + sa * cc, ca * cb]]


# ---------------- hem functions ----------------
def blk_hem(a):
    """black skirt hem (editor). front 17.4 / side 15.9 / back 14.4 (+ small front V notch)"""
    notch = 0.55 * max(0.0, (34.0 - abs(a)) / 34.0) ** 1.3
    return 15.9 + 1.5 * math.cos(math.radians(a)) + notch


def blue_hem(a):
    """petticoat hem centreline. front 15.85 / side 14.35 / back 12.85"""
    return 14.35 + 1.5 * math.cos(math.radians(a))


# ---------------- ring spec ----------------
def ang_set(N):
    return [-180.0 + (i + 0.5) * 360.0 / N for i in range(N)]


def bone_of(a):
    a = ((a + 180.0) % 360.0) - 180.0
    if abs(a) <= 45.0:
        return 'FrontSkirt'
    if 45.0 < a <= 135.0:
        return 'LeftSkirt'
    if -135.0 <= a < -45.0:
        return 'RightSkirt'
    return 'BackSkirt'


PLATES = []   # (bone, origin_editor, size, rot_editor, pivot_editor, uv, layer)


def add_ring(layer, N, yt, shape_t, yb_fn, shape_b, thick, wmul,
             color_fn, skip_fn=None, bone_fn=None):
    for i, a in enumerate(ang_set(N)):
        if skip_fn and skip_fn(a, i):
            continue
        yb = yb_fn(a)
        r_t = se_r(a, *shape_t)
        r_b = se_r(a, *shape_b)
        dy = yt - yb
        dr = r_b - r_t
        L = math.hypot(dy, dr)
        if L < 0.05:
            continue
        phi = math.atan2(dr, dy)
        rc = 0.5 * (r_t + r_b)
        W = 2.0 * math.pi * rc / N * wmul
        ar = math.radians(a)
        px = CX + rc * math.sin(ar)
        pz = CZ - rc * math.cos(ar)
        py = 0.5 * (yt + yb)
        X, Y, Z = basis(a, phi)
        R = [[X[0], Y[0], Z[0]], [X[1], Y[1], Z[1]], [X[2], Y[2], Z[2]]]
        assert max(abs(rebuild_rot(R)[i][j] - R[i][j]) for i in range(3) for j in range(3)) < 1e-6
        rot = euler_xyz(R)
        origin = (px - W / 2, py - L / 2, pz - thick / 2)
        bone = bone_fn(a) if bone_fn else bone_of(a)
        PLATES.append((layer, bone, origin, (W, L, thick), rot, (px, py, pz), color_fn(i, a)))


def alt(cols):
    return lambda i, a: UV[cols[i % len(cols)]]


# ---- R0 waistband (Skirt) : straddles the hip top, hugs it
add_ring('waistband', 16, 23.82, (3.24, 2.24, 3.8), lambda a: 23.42, (3.40, 2.52, 3.6),
         0.30, 1.18, alt(['black_dark', 'black_dark', 'black_light', 'black_dark']),
         bone_fn=lambda a: 'Skirt')

# ---- R1 lining cone (Skirt) : plugs every gap, sits behind everything
add_ring('lining', 14, 23.25, (2.90, 2.10, 3.4), lambda a: blk_hem(a) + 0.60, (3.80, 3.62, 2.1),
         0.30, 1.36, alt(['black_dark']), bone_fn=lambda a: 'Skirt')

# ---- R2 black tier 1 (upper cone)
add_ring('tier1', 16, 23.48, (3.10, 2.38, 3.6), lambda a: 21.10, (3.98, 3.62, 2.4),
         0.34, 1.22, alt(['black_mid', 'near_black']))

# ---- R3 black tier 2 (lower cone, continuous with tier1)
add_ring('tier2', 20, 21.12, (4.02, 3.66, 2.4), lambda a: blk_hem(a), (5.34, 5.14, 2.1),
         0.34, 1.30, alt(['black_dark', 'near_black2']))

# ---- R4 peplum flaps (waist ruffle, opens at centre front)
add_ring('peplum', 16, 23.46, (3.76, 2.92, 3.4), lambda a: 21.80 - (0.45 if abs(abs(a) - 33.75) < 1e-6 else 0.0),
         (4.62, 3.88, 2.4), 0.32, 1.28, alt(['black_light', 'black_mid']),
         skip_fn=lambda a, i: abs(a) < 14.0)

# ---- R4b upper hem ruffle band (hem-relative, sits above frill2)
for i, a in enumerate(ang_set(16)):
    yt = blk_hem(a) + 2.10
    yb = blk_hem(a) + 1.15
    r_t, r_b = 5.20, 5.48
    dy, dr = yt - yb, r_b - r_t
    L = math.hypot(dy, dr)
    phi = math.atan2(dr, dy)
    rc = 0.5 * (r_t + r_b)
    W = 2 * math.pi * rc / 16 * 1.32
    ar = math.radians(a)
    px, pz, py = CX + rc * math.sin(ar), CZ - rc * math.cos(ar), 0.5 * (yt + yb)
    X, Y, Z = basis(a, phi)
    rot = euler_xyz([[X[0], Y[0], Z[0]], [X[1], Y[1], Z[1]], [X[2], Y[2], Z[2]]])
    PLATES.append(('frill1', bone_of(a), (px - W / 2, py - L / 2, pz - 0.16), (W, L, 0.32), rot,
                   (px, py, pz), UV['black_light' if i % 2 == 0 else 'black_mid']))

# ---- R5 ruffle at tier2 hem (lower frill)
add_ring('frill2', 20, lambda a: 0.0, (5.44, 5.24, 2.2), lambda a: 0.0, (5.96, 5.74, 2.1),
         0.32, 1.34, alt(['black_light', 'black_mid'])) if False else None

# frill2 needs hem-relative heights -> build manually
for i, a in enumerate(ang_set(20)):
    yb = blk_hem(a) + 0.02
    yt = blk_hem(a) + 1.18
    r_t = 5.30
    r_b = 5.72
    dy, dr = yt - yb, r_b - r_t
    L = math.hypot(dy, dr)
    phi = math.atan2(dr, dy)
    rc = 0.5 * (r_t + r_b)
    W = 2 * math.pi * rc / 20 * 1.34
    ar = math.radians(a)
    px, pz, py = CX + rc * math.sin(ar), CZ - rc * math.cos(ar), 0.5 * (yt + yb)
    X, Y, Z = basis(a, phi)
    R = [[X[0], Y[0], Z[0]], [X[1], Y[1], Z[1]], [X[2], Y[2], Z[2]]]
    rot = euler_xyz(R)
    PLATES.append(('frill2', bone_of(a), (px - W / 2, py - L / 2, pz - 0.16), (W, L, 0.32), rot,
                   (px, py, pz), UV['black_light' if i % 2 == 0 else 'black_mid']))

# ---- R6 blue striped petticoat
add_ring('petticoat', 24, lambda a: 0.0, (4.90, 4.72, 2.2), lambda a: 0.0, (5.52, 5.34, 2.1),
         0.30, 1.24, alt(['blue_deep', 'blue_mid', 'blue_deep', 'blue_light'])) if False else None

for i, a in enumerate(ang_set(24)):
    yt = blk_hem(a) + 0.75
    yb = blue_hem(a) + 0.85
    r_t = se_r(a, 4.35, 4.17, 2.2)
    r_b = se_r(a, 5.05, 4.87, 2.1)
    dy, dr = yt - yb, r_b - r_t
    L = math.hypot(dy, dr)
    phi = math.atan2(dr, dy)
    rc = 0.5 * (r_t + r_b)
    W = 2 * math.pi * rc / 24 * 1.24
    ar = math.radians(a)
    px, pz, py = CX + rc * math.sin(ar), CZ - rc * math.cos(ar), 0.5 * (yt + yb)
    X, Y, Z = basis(a, phi)
    rot = euler_xyz([[X[0], Y[0], Z[0]], [X[1], Y[1], Z[1]], [X[2], Y[2], Z[2]]])
    cols = ['blue_deep', 'blue_mid', 'blue_deep', 'blue_mid', 'blue_deep', 'blue_light']
    PLATES.append(('petticoat', bone_of(a), (px - W / 2, py - L / 2, pz - 0.15), (W, L, 0.30), rot,
                   (px, py, pz), UV[cols[i % len(cols)]]))

# ---- R7 blue ruffle at petticoat hem
for i, a in enumerate(ang_set(24)):
    yt = blue_hem(a) + 1.12
    yb = blue_hem(a) + 0.18
    r_t, r_b = 5.00, 5.30
    dy, dr = yt - yb, r_b - r_t
    L = math.hypot(dy, dr)
    phi = math.atan2(dr, dy)
    rc = 0.5 * (r_t + r_b)
    W = 2 * math.pi * rc / 24 * 1.45
    ar = math.radians(a)
    px, pz, py = CX + rc * math.sin(ar), CZ - rc * math.cos(ar), 0.5 * (yt + yb)
    X, Y, Z = basis(a, phi)
    rot = euler_xyz([[X[0], Y[0], Z[0]], [X[1], Y[1], Z[1]], [X[2], Y[2], Z[2]]])
    PLATES.append(('bluefrill', bone_of(a), (px - W / 2, py - L / 2, pz - 0.15), (W, L, 0.30), rot,
                   (px, py, pz), UV['blue_mid' if i % 2 == 0 else 'blue_deep']))

# ---- R8 pale narrow edge (bottom-most)
for i, a in enumerate(ang_set(24)):
    yt = blue_hem(a) + 0.30
    yb = blue_hem(a) - 0.32
    r_t, r_b = 5.36, 5.41
    dy, dr = yt - yb, r_b - r_t
    L = math.hypot(dy, dr)
    phi = math.atan2(dr, dy)
    rc = 0.5 * (r_t + r_b)
    W = 2 * math.pi * rc / 24 * 1.50
    ar = math.radians(a)
    px, pz, py = CX + rc * math.sin(ar), CZ - rc * math.cos(ar), 0.5 * (yt + yb)
    X, Y, Z = basis(a, phi)
    rot = euler_xyz([[X[0], Y[0], Z[0]], [X[1], Y[1], Z[1]], [X[2], Y[2], Z[2]]])
    col = 'blue_white' if i % 4 == 3 else 'blue_pale'
    PLATES.append(('edge', bone_of(a), (px - W / 2, py - L / 2, pz - 0.14), (W, L, 0.28), rot,
                   (px, py, pz), UV[col]))

# ---- R9 back bustle over-panel
for a in (144.0, 162.0, 180.0, 198.0, 216.0):
    yt = 22.55
    yb = 19.55
    r_t = se_r(a, 4.75, 4.48, 2.35)
    r_b = se_r(a, 5.65, 5.34, 2.2)
    dy, dr = yt - yb, r_b - r_t
    L = math.hypot(dy, dr)
    phi = math.atan2(dr, dy)
    rc = 0.5 * (r_t + r_b)
    W = 2 * math.pi * rc / 15 * 1.25
    ar = math.radians(a)
    px, pz, py = CX + rc * math.sin(ar), CZ - rc * math.cos(ar), 0.5 * (yt + yb)
    X, Y, Z = basis(a, phi)
    rot = euler_xyz([[X[0], Y[0], Z[0]], [X[1], Y[1], Z[1]], [X[2], Y[2], Z[2]]])
    col = 'black_mid' if abs(a) in (144.0, 198.0) else ('black_light' if a == 180.0 else 'black_mid')
    PLATES.append(('bustle', 'BackSkirt', (px - W / 2, py - L / 2, pz - 0.18), (W, L, 0.36), rot,
                   (px, py, pz), UV['black_light' if a in (162.0, 198.0) else 'black_mid']))

# ---- R10 centre-front V fill (sits under the peplum opening)
for a in (-8.0, 8.0):
    yt, yb = 23.05, 21.45
    r_t, r_b = 3.78, 4.35
    dy, dr = yt - yb, r_b - r_t
    L = math.hypot(dy, dr)
    phi = math.atan2(dr, dy)
    rc = 0.5 * (r_t + r_b)
    W = 2 * math.pi * rc / 24 * 1.20
    ar = math.radians(a)
    px, pz, py = CX + rc * math.sin(ar), CZ - rc * math.cos(ar), 0.5 * (yt + yb)
    X, Y, Z = basis(a, phi)
    rot = euler_xyz([[X[0], Y[0], Z[0]], [X[1], Y[1], Z[1]], [X[2], Y[2], Z[2]]])
    PLATES.append(('vfill', 'FrontSkirt', (px - W / 2, py - L / 2, pz - 0.15), (W, L, 0.30), rot,
                   (px, py, pz), UV['black_dark' if a < 0 else 'black_mid']))

# ---------------- stats / checks ----------------
def plate_profile(p):
    """returns (azimuth, r_at_y function params) using the reconstructed basis."""
    a = math.degrees(math.atan2(p[5][0] - CX, -(p[5][2] - CZ)))
    R = rebuild_rot_from_deg(p[4])
    Y = [R[0][1], R[1][1], R[2][1]]
    ar = math.radians(a)
    u = (math.sin(ar), 0.0, -math.cos(ar))
    tphi = -(Y[0] * u[0] + Y[1] * u[1] + Y[2] * u[2]) / Y[1]
    rc = math.hypot(p[5][0] - CX, p[5][2] - CZ)
    return a, rc, tphi


def rebuild_rot_from_deg(rot):
    a, b, c = (math.radians(v) for v in rot)
    ca, sa = math.cos(a), math.sin(a)
    cb, sb = math.cos(b), math.sin(b)
    cc, sc = math.cos(c), math.sin(c)
    return [[cb * cc, -cb * sc, sb],
            [sa * sb * cc + ca * sc, -sa * sb * sc + ca * cc, -sa * cb],
            [-ca * sb * cc + sa * sc, ca * sb * sc + sa * cc, ca * cb]]


def stats():
    print('total plates', len(PLATES))
    from collections import Counter
    print('by bone', dict(Counter(p[1] for p in PLATES)))
    print('by layer', dict(Counter(p[0] for p in PLATES)))
    piv = lambda p: p[5]
    siz = lambda p: p[3]
    for layer_name in ['waistband', 'tier1', 'edge']:
        sel = [p for p in PLATES if p[0] == layer_name]
        if not sel:
            continue
        cxs = [piv(p)[0] for p in sel]
        czs = [piv(p)[2] for p in sel]
        ys = [piv(p)[1] for p in sel]
        print(f'{layer_name}: centre x={sum(cxs)/len(cxs):+.3f} z={sum(czs)/len(czs):+.3f} '
              f'y[{min(ys)-siz(sel[0])[1]/2:.2f},{max(ys)+siz(sel[0])[1]/2:.2f}] (body cx {BODY_CX})')
    def azim(p):
        return math.degrees(math.atan2(piv(p)[0] - CX, -(piv(p)[2] - CZ)))
    def low_at(layer_name, target):
        sel = [p for p in PLATES if p[0] == layer_name]
        best = min(sel, key=lambda p: abs((azim(p) - target + 180) % 360 - 180))
        return piv(best)[1] - siz(best)[1] / 2, azim(best)
    for label, tgt in [('front', 0.0), ('side', 90.0), ('back', 180.0)]:
        e, ea = low_at('edge', tgt)
        b, ba = low_at('frill2', tgt)
        print(f'hem {label}: blue/pale {e:.2f} (az {ea:.0f})  black frill {b:.2f} (az {ba:.0f})')
    err = 0.0
    bad = 0
    for p in PLATES:
        ox, oy, oz = piv(p)
        twin = [q for q in PLATES if q[0] == p[0] and abs(piv(q)[0] - (2 * CX - ox)) < 0.02
                and abs(piv(q)[1] - oy) < 0.02 and abs(piv(q)[2] - oz) < 0.02]
        if not twin:
            bad += 1
    print('mirror missing pairs:', bad)
    tri = sum(1 for p in PLATES if all(abs(v) > 0.5 for v in p[4]))
    print(f'3-axis {tri}/{len(PLATES)} = {100.0 * tri / len(PLATES):.1f}%')
    rtop = [math.hypot(piv(p)[0] - CX, piv(p)[2] - CZ) for p in PLATES if p[0] == 'waistband']
    rbot = [math.hypot(piv(p)[0] - CX, piv(p)[2] - CZ) for p in PLATES if p[0] == 'edge']
    print(f'top ring r[{min(rtop):.2f},{max(rtop):.2f}]  bottom ring r[{min(rbot):.2f},{max(rbot):.2f}]')
    warn = 0
    prof = [plate_profile(p) for p in PLATES]
    for i in range(len(PLATES)):
        for j in range(i + 1, len(PLATES)):
            a, b = PLATES[i], PLATES[j]
            if a[0] == b[0]:
                continue
            ya = (piv(a)[1] - siz(a)[1] / 2, piv(a)[1] + siz(a)[1] / 2)
            yb = (piv(b)[1] - siz(b)[1] / 2, piv(b)[1] + siz(b)[1] / 2)
            ov = min(ya[1], yb[1]) - max(ya[0], yb[0])
            if ov < 0.25:
                continue
            ym = 0.5 * (max(ya[0], yb[0]) + min(ya[1], yb[1]))
            ra = prof[i][1] - (ym - piv(a)[1]) * prof[i][2]
            rb = prof[j][1] - (ym - piv(b)[1]) * prof[j][2]
            gap = abs(ra - rb) - (siz(a)[2] + siz(b)[2]) / 2
            d = abs((prof[i][0] - prof[j][0] + 180) % 360 - 180)
            if gap < -0.10 and d < 14:
                warn += 1
    print('radial intersections (rough):', warn)
    if '--diag' in sys.argv:
        for p, pr in zip(PLATES, prof):
            if not all(abs(v) > 0.5 for v in p[4]):
                print('  low-rot', p[0], p[1], 'rot', [round(v, 2) for v in p[4]])
        pairs = []
        for i in range(len(PLATES)):
            for j in range(i + 1, len(PLATES)):
                a, b = PLATES[i], PLATES[j]
                if a[0] == b[0]:
                    continue
                ya = (piv(a)[1] - siz(a)[1] / 2, piv(a)[1] + siz(a)[1] / 2)
                yb = (piv(b)[1] - siz(b)[1] / 2, piv(b)[1] + siz(b)[1] / 2)
                ov = min(ya[1], yb[1]) - max(ya[0], yb[0])
                if ov < 0.25:
                    continue
                ym = 0.5 * (max(ya[0], yb[0]) + min(ya[1], yb[1]))
                ra = prof[i][1] - (ym - piv(a)[1]) * prof[i][2]
                rb = prof[j][1] - (ym - piv(b)[1]) * prof[j][2]
                gap = abs(ra - rb) - (siz(a)[2] + siz(b)[2]) / 2
                d = abs((prof[i][0] - prof[j][0] + 180) % 360 - 180)
                if gap < -0.10 and d < 14:
                    pairs.append((round(gap, 2), a[0], b[0], round(d, 1), round(ym, 2)))
        pairs.sort()
        for pr in pairs[:24]:
            print('  X', pr)


stats()

if '--dry' in sys.argv:
    sys.exit(0)

# ---------------- write main.json ----------------
data = json.load(open(P, encoding='utf-8'))
geo = data['minecraft:geometry'][0]
bones = geo['bones']
KEEP = {'Skirt', 'FrontSkirt', 'BackSkirt', 'LeftSkirt', 'RightSkirt'}
PIVOT = {
    'Skirt':      [CX, 23.85, CZ],
    'FrontSkirt': [CX, 23.80, -2.50],
    'BackSkirt':  [CX, 23.80, 2.50],
    'LeftSkirt':  [CX + 3.30, 23.80, 0.0],
    'RightSkirt': [CX - 3.30, 23.80, 0.0],
}
for b in bones:
    if b['name'] in KEEP:
        b['cubes'] = []
        pv = PIVOT[b['name']]
        b['pivot'] = [-pv[0], pv[1], pv[2]]   # json bone pivot is x-mirrored too

BY_BONE = {k: [] for k in KEEP}
for layer, bone, org, size, rot, piv, uv in PLATES:
    jorg = [-(org[0] + size[0]), org[1], org[2]]
    jrot = [-rot[0], -rot[1], rot[2]]
    jpiv = [-piv[0], piv[1], piv[2]]
    cube = {
        'origin': [round(v, 4) for v in jorg],
        'size': [round(v, 4) for v in size],
        'rotation': [round(v, 4) for v in jrot],
        'pivot': [round(v, 4) for v in jpiv],
        'uv': list(uv),
    }
    BY_BONE[bone].append(cube)

for b in bones:
    if b['name'] in KEEP:
        b['cubes'] = BY_BONE[b['name']]

shutil.copyfile(P, P + '.v6bak')
json.dump(data, open(P, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('written', P)
print('counts', {k: len(v) for k, v in BY_BONE.items()}, 'sum', sum(len(v) for v in BY_BONE.values()))
