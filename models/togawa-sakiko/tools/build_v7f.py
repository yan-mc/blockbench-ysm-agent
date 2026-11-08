import json, os, math, shutil, collections
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
P = os.path.join(BASE, "pack", "models", "main.json")
OUT = os.path.join(BASE, "artifacts", "v7f")
os.makedirs(os.path.join(OUT, "_presave"), exist_ok=True)
BAK = os.path.join(OUT, "_presave", "main_v7e.json")
if os.path.exists(BAK):
    shutil.copy2(BAK, P)            # always rebuild from the v7e base
else:
    shutil.copy2(P, BAK)

d = json.load(open(P, encoding="utf-8"))
G = d["minecraft:geometry"][0]
bones = {b["name"]: b for b in G["bones"]}
R = math.radians

def add(a, b): return [a[0]+b[0], a[1]+b[1], a[2]+b[2]]
def sub(a, b): return [a[0]-b[0], a[1]-b[1], a[2]-b[2]]
def dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def cross(a, b): return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
def norm(a):
    l = math.sqrt(dot(a, a)) or 1.0
    return [a[0]/l, a[1]/l, a[2]/l]

def euler(X, Y, Z):
    M = [[X[i], Y[i], Z[i]] for i in range(3)]
    sb = max(-1.0, min(1.0, M[0][2])); b = math.asin(sb); cb = math.cos(b)
    if abs(cb) < 1e-6:
        a = 0.0; c = math.atan2(M[1][0], M[1][1])
    else:
        a = math.atan2(-M[1][2], M[2][2]); c = math.atan2(-M[0][1], M[0][0])
    return [round(math.degrees(a), 3), round(math.degrees(b), 3), round(math.degrees(c), 3)]

def uvsw(x): return {f: {"uv": [x, 246], "uv_size": [3, 3]} for f in ("north", "east", "south", "west", "up", "down")}

def cube(center, size, X, Y, Z, xuv):
    c = [round(v, 4) for v in center]; s = [round(v, 4) for v in size]
    return {"origin": [round(c[i]-s[i]/2, 4) for i in range(3)], "size": s, "pivot": c,
            "rotation": euler(norm(X), norm(Y), norm(Z)), "uv": uvsw(xuv)}

def flat(center, sx, sz, th, xuv):
    return cube(center, [sx, sz, th], [1, 0, 0], [0, 0, 1], [0, -1, 0], xuv)

def vplate(center, w, h, th, xuv):
    return cube(center, [w, h, th], [1, 0, 0], [0, -1, 0], [0, 0, -1], xuv)

REF = [0, 0, 1]
def basis_from_dir(down):
    Y = norm(down); X = norm(cross(Y, REF)); Z = norm(cross(X, Y)); return X, Y, Z

rep = {}

# ============================================================ 1) HairCap crown
cap_old = bones["HairCap"]["cubes"]
assert len(cap_old) == 179, len(cap_old)
shell = [dict(c) for c in cap_old[:122]]          # v7d shell kept in v7e
R2 = dict()                                        # keep rotation labels for report

# (a) lower the 5 upper side plates that poke into the old dome (top 41.51 -> 41.16)
LOWER = {93: 0.35, 94: 0.35, 98: 0.35, 99: 0.35, 103: 0.35}
for i, dy in LOWER.items():
    c = shell[i]; c["origin"] = [c["origin"][0], round(c["origin"][1]-dy, 4), c["origin"][2]]
    c["pivot"] = [c["pivot"][0], round(c["pivot"][1]-dy, 4), c["pivot"][2]]

# (b) pull the 4 corner 45-deg plates 0.85 inward (they reached r 5.7-6.16)
PULL = [106, 109, 112, 115]
for i in PULL:
    c = shell[i]
    cx, cz = c["pivot"][0], c["pivot"][2]
    rr = math.hypot(cx, cz)
    ux, uz = cx/rr, cz/rr
    c["origin"] = [round(c["origin"][0]-0.85*ux, 4), c["origin"][1], round(c["origin"][2]-0.85*uz, 4)]
    c["pivot"] = [round(cx-0.85*ux, 4), c["pivot"][1], round(cz-0.85*uz, 4)]

# (c) delete the four diagonal "corner" boxes (r 6.0, y39.4-40.3)
DROP_CORNER = {118, 119, 120, 121}
shell = [c for i, c in enumerate(shell) if i not in DROP_CORNER]

# (d) new crown: lathe dome tangent to an elliptical paraboloid (no shingle steps)
AX, BZ_BACK, BZ_FRONT = 4.78, 4.80, 4.02
H0, KK = 42.36, 1.70

def surf(s, phi):
    bz = BZ_BACK if math.sin(phi) >= 0 else BZ_FRONT
    return [AX*s*math.cos(phi), H0-KK*s*s, bz*s*math.sin(phi)]

def s_normal(s, phi, eps=2e-3):
    s0, s1 = max(0.0, s-eps), min(1.0, s+eps)
    Ts = sub(surf(s1, phi), surf(s0, phi))
    Tp = sub(surf(s, phi+eps), surf(s, phi-eps))
    N = norm(cross(Tp, Ts))
    if N[1] < 0: N = [-N[0], -N[1], -N[2]]
    return norm(Tp), N

TH = 0.22
RINGS = [(0.12, 0.34, 8), (0.34, 0.54, 12), (0.54, 0.74, 14), (0.74, 0.88, 16), (0.88, 1.00, 18)]
dome = []
dome.append(flat([0, H0-TH/2, 0], 1.15, 1.15, TH, 86))
dome.append(flat([0, 41.68, 0], 3.05, 3.05, TH, 86))       # hidden inner seal (no pinholes)
for k, (s0, s1, nsec) in enumerate(RINGS):
    rho = (s0+s1)/2
    for j in range(nsec):
        phm = 2*math.pi*(j+0.5*(k % 2))/nsec
        dph = math.pi/nsec
        P0 = surf(s0, phm); P1 = surf(s1, phm)
        Lr = math.hypot(P1[0]-P0[0], P1[2]-P0[2]) + 0.30          # radial len + overlap
        Pa, Pb = surf(rho, phm-dph), surf(rho, phm+dph)
        Pm = surf(rho, phm)
        w = math.hypot(Pb[0]-Pa[0], Pb[2]-Pa[2]) * 1.26            # real sector chord + 26%
        Xt, N = s_normal(rho, phm)
        c = [Pm[0]-N[0]*TH/2, Pm[1]-N[1]*TH/2, Pm[2]-N[2]*TH/2]
        xuv = 86 if rho < 0.5 else (70 if rho < 0.78 else 54)
        dome.append(cube(c, [w, TH, Lr], Xt, N, cross(Xt, N), xuv))
bones["HairCap"]["cubes"] = shell + dome
rep["HairCap"] = {"kept": len(shell), "lowered": len(LOWER), "deleted": len(DROP_CORNER),
                  "pulled_in": len(PULL), "dome": len(dome), "total": len(shell)+len(dome)}

# hidden second layer under the dome: different sector counts so no seam can line up
under = []
for (s0, s1, nsec) in [(0.08, 0.55, 14), (0.55, 1.02, 16)]:
    rho = (s0+s1)/2
    for j in range(nsec):
        phm = 2*math.pi*(j+0.37)/nsec
        dph = math.pi/nsec
        P0 = surf(s0, phm); P1 = surf(s1, phm)
        Lr = math.hypot(P1[0]-P0[0], P1[2]-P0[2]) + 0.35
        Pa, Pb = surf(rho, phm-dph), surf(rho, phm+dph)
        Pm = surf(rho, phm)
        w = math.hypot(Pb[0]-Pa[0], Pb[2]-Pa[2]) * 1.30
        Xt, N = s_normal(rho, phm)
        off = TH/2 + 0.14
        c = [Pm[0]-N[0]*off, Pm[1]-N[1]*off, Pm[2]-N[2]*off]
        under.append(cube(c, [w, TH, Lr], Xt, N, cross(Xt, N), 70 if rho < 0.7 else 54))
bones["HairCap"]["cubes"] = shell + dome + under
rep["HairCap"]["underlayer"] = len(under)
rep["HairCap"]["total"] = len(shell)+len(dome)+len(under)

# ============================================================ 2) HairBack: 9 bent locks
def strand(x0, z0, top, tip, w0, dep, n, Ax, Az, Bow, splay, px, pz, mirror,
           wprof=None, ov=0.25, uvbands=(0.28, 0.70), uvcols=(54, 38, 22), tuck=0.55, tuck_span=7.4):
    L = top - tip
    def path(t):
        x = mirror*(x0*(1.0+splay*t) + Ax*math.sin(2*math.pi*(t+px)))
        z = z0 - tuck*max(0.0, min(1.0, (top-(top-L*t))/tuck_span)) \
            + Az*math.sin(2*math.pi*(t+pz)) + Bow*math.sin(math.pi*t)
        y = top - L*t
        return [x, y, z]
    cs = []
    dirs = []
    offs = []
    for i in range(n):
        t0 = max(0.0, (i-0.5)/n); t1 = min(1.0, (i+1.5)/n)
        tc = (i+0.5)/n
        d = norm(sub(path(t1), path(t0)))
        h = abs(t1-t0)*L + ov
        w = w0*(wprof[i] if wprof else 1.0)
        Xb, Yb, Zb = basis_from_dir(d)
        p = path(tc)
        uv = uvcols[0] if tc < uvbands[0] else (uvcols[1] if tc < uvbands[1] else uvcols[2])
        cs.append(cube(p, [w, h, dep], Xb, Yb, Zb, uv))
        dirs.append(d)
    for i in range(n-1):
        offs.append([abs(path((i+1.5)/n)[0]-path((i+1.5)/n)[0]), 0])
    return cs, dirs

rep["HairBack"] = []
hb = []
hb_dirs = []
def zc_of(x): return 5.28 - 0.058*x*x
WP = [1.0, 1.0, 1.0, 0.98, 0.94, 0.88, 0.76, 0.60]
locks_b = [
    # x0,  w0,   dep,  tip,  zoff,  Ax,   Az,   Bow, splay, px,   pz
    (0.00, 1.40, 1.20, 20.6, 0.00, 0.34, 0.58, 0.42, 0.02, 0.02, 0.27),
    (1.00, 1.28, 0.80, 23.4, 0.14, 0.42, 0.46, 0.34, 0.10, 0.24, 0.49),
    (2.00, 1.16, 1.04, 21.2, -0.12, 0.36, 0.66, 0.55, 0.14, 0.43, 0.68),
    (3.00, 1.10, 0.92, 24.8, 0.10, 0.46, 0.52, 0.36, 0.10, 0.65, 0.90),
    (3.95, 0.96, 1.10, 22.6, -0.16, 0.44, 0.60, 0.45, 0.12, 0.83, 0.08),
]
TOP_B = 39.40
hb_locks = []
for (x0, w0, dep, tip, zoff, Ax, Az, Bow, splay, px, pz) in locks_b:
    for s in ((1,) if x0 == 0 else (1, -1)):
        cs, ds = strand(x0, zc_of(x0)+zoff, TOP_B, tip, w0, dep, 8, Ax, Az, Bow, splay, px, pz, s,
                        wprof=WP, ov=0.26, uvcols=(54, 38, 22))
        hb += cs
        hb_dirs.append(ds)
        hb_locks.append((cs, ds))
        rep["HairBack"].append({"x0": s*x0, "tip": tip, "w": w0, "dep": dep, "n": 8})
# inner backing curtain (2 rows, continuous, closes every slit between locks)
for (xs, wt, y0, y1, dz) in [
        ([0.0, 1.15, 2.30, 3.40, 4.40], 1.46, 29.0, 39.85, -0.18),   # upper row
        ([0.0, 1.10, 2.20, 3.20, 4.30], 1.40, 20.90, 30.10, -0.26)]:  # lower row
    for xa in xs:
        for s in ((1,) if xa == 0 else (1, -1)):
            h = y1-y0
            hb.append(vplate([s*xa, (y0+y1)/2, zc_of(xa)+dz], wt, h, 0.50, 22 if y0 > 25 else 22))
# extra seam fillers behind the widest lateral swings
for (x0, z0, y0, y1, w) in [(0.55, 0.0, 33.0, 39.6, 1.30), (-0.55, 0.0, 33.0, 39.6, 1.30)]:
    hb.append(vplate([x0, (y0+y1)/2, zc_of(abs(x0))-0.62], w, y1-y0, 0.42, 22))
bones["HairBack"]["cubes"] = hb

# ============================================================ 3) hl_side: 3 bent locks / side
hs = []
hs_dirs = []
hs_locks = []
def strand_side(x0, z0, top, tip, w0, dep, n, Ax, Az, Bow, splay, px, pz, mirror):
    return strand(x0, z0, top, tip, w0, dep, n, Ax, Az, Bow, splay, px, pz, mirror,
                  wprof=[1.0, 1.0, 0.98, 0.92, 0.84, 0.68][:n], ov=0.24, uvcols=(70, 54, 38),
                  uvbands=(0.35, 0.75), tuck=0.0, tuck_span=1.0)
locks_s = [
    # x0,   z0,    w0,   dep,  tip,  Ax,   Az,   Bow, splay, px,   pz
    (3.98, -1.55, 0.86, 0.70, 27.0, 0.30, 0.36, 0.36, 0.16, 0.10, 0.30),
    (4.42, -0.10, 0.92, 0.78, 23.6, 0.38, 0.44, 0.48, 0.20, 0.38, 0.66),
    (4.66, 1.40, 0.88, 0.74, 22.6, 0.34, 0.48, 0.44, 0.18, 0.62, 0.14),
]
for (x0, z0, w0, dep, tip, Ax, Az, Bow, splay, px, pz) in locks_s:
    for s in (1, -1):
        cs, ds = strand_side(x0, z0, 37.35, tip, w0, dep, 6, Ax, Az, Bow, splay, px, pz, s)
        hs += cs
        hs_dirs.append(ds)
        hs_locks.append((cs, ds))
bones["hl_side"]["cubes"] = hs
rep["hl_side"] = {"locks": 6, "segs": 6, "cubes": len(hs)}

# ============================================================ diagnostics
def ang(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(norm(a), norm(b))))))

def stats(dirsets, label):
    j3 = []
    for ds in dirsets:
        for i in range(len(ds)-1): j3.append(ang(ds[i], ds[i+1]))
    j3s = sorted(j3)
    inband = sum(1 for v in j3 if 5.0 <= v <= 12.0)
    print(f"{label}: joints={len(j3)} mean={sum(j3)/len(j3):.2f} min={j3s[0]:.2f} max={j3s[-1]:.2f} "
          f"in[5,12]={100.0*inband/len(j3):.0f}% p25={j3s[len(j3)//4]:.2f} p75={j3s[3*len(j3)//4]:.2f}")
    return {"n": len(j3), "mean": round(sum(j3)/len(j3), 2), "min": round(j3s[0], 2), "max": round(j3s[-1], 2),
            "inband_pct": round(100.0*inband/len(j3), 1)}

rep["back_joint"] = stats(hb_dirs, "HairBack joint-angle")
rep["side_joint"] = stats(hs_dirs, "hl_side joint-angle")

# per-segment tilt diffs: tilt about X (forward/back) and about Z (lateral) of each segment axis
def tilt(d):
    ty = math.degrees(math.atan2(-d[2], -d[1]))
    tx = math.degrees(math.atan2(d[0], -d[1]))
    return tx, ty

def rotdiff(locks, label):
    dxs = []; dys = []; offx = []; offz = []
    for cs, ds in locks:
        t = [tilt(x) for x in ds]
        for i in range(len(t)-1):
            dxs.append(abs(t[i+1][0]-t[i][0])); dys.append(abs(t[i+1][1]-t[i][1]))
        for i in range(len(cs)-1):
            offx.append(abs(cs[i+1]["pivot"][0]-cs[i]["pivot"][0]))
            offz.append(abs(cs[i+1]["pivot"][2]-cs[i]["pivot"][2]))
    f = lambda v: (round(sum(v)/len(v), 2), round(min(v), 2), round(max(v), 2))
    print(f"{label}: dTiltZ(X-axis) mean/min/max={f(dys)}  dTiltX(Z-axis)={f(dxs)}")
    print(f"{label}: seg centre |dx| mean/min/max={f(offx)}  |dz|={f(offz)}")
    return {"dTiltZ": f(dys), "dTiltX": f(dxs), "seg_dx": f(offx), "seg_dz": f(offz)}
rep["back_rotdiff"] = rotdiff(hb_locks, "HairBack")
rep["side_rotdiff"] = rotdiff(hs_locks, "hl_side")

total = sum(len(b.get("cubes", [])) for b in G["bones"])
rep["total_cubes"] = total; rep["bones"] = len(G["bones"])
print("\nGROUPS:", json.dumps({k: v for k, v in rep.items() if isinstance(v, dict) and k not in ("back_joint", "side_joint")}, ensure_ascii=False))
print("TOTAL cubes", total, "bones", len(G["bones"]))

json.dump(d, open(P, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("written", P, os.path.getsize(P))
