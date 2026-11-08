import json, math, shutil, os

P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
BAK = P + ".v7a-bak"

x0 = -0.15
Y_TOP = 23.55
COS = math.cos
SIN = math.sin

def ell(rx, rz, phi):
    return (rx * SIN(phi), -rz * COS(phi))  # (x, z) offset from x0

def frame(t, u):
    # t: tangent, u: up along surface
    t = [t[0], t[1], t[2]]
    n = math.sqrt(sum(v*v for v in t)); t = [v/n for v in t]
    d = sum(t[i]*u[i] for i in range(3))
    u2 = [u[i] - d*t[i] for i in range(3)]
    n = math.sqrt(sum(v*v for v in u2)); u2 = [v/n for v in u2]
    z = [t[1]*u2[2]-t[2]*u2[1], t[2]*u2[0]-t[0]*u2[2], t[0]*u2[1]-t[1]*u2[0]]
    return [t, u2, z]

def euler_zyx(R):
    # Blockbench Format.euler_order = "ZYX" -> R = Rz(rz)*Ry(ry)*Rx(rx)
    # R20 = -sin(ry); R21 = sin(rx)cos(ry); R22 = cos(rx)cos(ry)
    # R10 = cos(ry)sin(rz); R00 = cos(ry)cos(rz)
    s = max(-1.0, min(1.0, -R[2][0]))
    b = math.asin(s)
    if abs(R[2][0]) < 0.999999:
        a = math.atan2(R[2][1], R[2][2])
        c = math.atan2(R[1][0], R[0][0])
    elif R[2][0] >= 0:  # ry = -90
        b = -math.pi/2
        a = math.atan2(-R[0][1], -R[0][2])
        c = 0.0
    else:  # ry = +90
        b = math.pi/2
        a = math.atan2(R[0][1], R[0][2])
        c = 0.0
    return [math.degrees(a), math.degrees(b), math.degrees(c)]

def cube(bone, center, size, R, uv, name=None):
    # center/size/R are in BLOCKBENCH space (front = -z, x as in preview).
    # Bedrock main.json stores mirrored x and negated rx/ry (see bedrock.js parseCube).
    rx, ry, rz = euler_zyx(R)
    mx = -(center[0] + size[0]/2)
    my = center[1] - size[1]/2
    mz = center[2] - size[2]/2
    cc = {
        "origin": [round(mx, 4), round(my, 4), round(mz, 4)],
        "size": [round(v, 4) for v in size],
        "pivot": [round(-center[0], 4), round(center[1], 4), round(center[2], 4)],
        "rotation": [round(-rx, 3), round(-ry, 3), round(rz, 3)],
        "uv": uv,
    }
    return bone, cc

def panel(phi, rx_top, rz_top, y_top, r_bot, y_bot, width, thick, uv, bone, ext_top=0.3, ext_bot=0.0):
    tx, tz = ell(rx_top, rz_top, phi)
    Ptop = [x0 + tx, y_top, tz]
    Pbot = [x0 + r_bot*SIN(phi), y_bot, -r_bot*COS(phi)]
    dx = [Ptop[i]-Pbot[i] for i in range(3)]
    L0 = math.sqrt(sum(v*v for v in dx))
    u = [v/L0 for v in dx]
    # extend top along u
    Ptop2 = [Ptop[i] + ext_top*u[i] for i in range(3)]
    Pbot2 = [Pbot[i] - ext_bot*u[i] for i in range(3)]
    L = L0 + ext_top + ext_bot
    center = [(Ptop2[i]+Pbot2[i])/2 for i in range(3)]
    t = [COS(phi), 0.0, SIN(phi)]
    R = frame(t, u)
    return cube(bone, center, [width, L, thick], R, uv)

def vband(phi, rx_top, rz_top, y_top, r_bot, y_bot, width, thick, uv, bone, ext_top=0.3):
    # vertical band: u=(0,1,0), center at mid of top/bottom ellipse radius
    Ptop = [x0 + rx_top*SIN(phi), y_top, -rz_top*COS(phi)]
    Pbot = [x0 + r_bot*SIN(phi), y_bot, -r_bot*COS(phi)]
    center = [(Ptop[0]+Pbot[0])/2, (Ptop[1]+Pbot[1])/2 + ext_top/2, (Ptop[2]+Pbot[2])/2]
    H = (y_top - y_bot) + ext_top
    t = [COS(phi), 0.0, SIN(phi)]
    R = frame(t, [0, 1, 0])
    return cube(bone, center, [width, H, thick], R, uv)

# ---- colors (flat swatch anchors) ----
C_BLACK = [200, 18]      # 38,34,48
C_DARK  = [226, 18]      # 23,21,28
C_MID   = [258, 18]      # 51,47,58
C_BLUE  = [178, 226]     # 169,198,232 light periwinkle
C_WHITE = [162, 226]     # 228,238,251

def quad_bone(phi):
    deg = math.degrees(phi) % 360
    if deg <= 45 or deg >= 315: return "FrontSkirt"
    if deg < 135: return "RightSkirt"
    if deg < 225: return "BackSkirt"
    return "LeftSkirt"

def radius_bot(phi):
    # outer hem radius of black bell (front 5.60 / side 5.90 / back 5.36)
    return 5.68 + 0.10*COS(phi) - 0.22*math.cos(2*phi)

def y_hem_bell(phi):
    return 14.10 + 1.50*COS(phi)

def y_hem_blue(phi):
    return 13.35 + 0.80*COS(phi)

new = {}  # bone -> list

def add(bone, c):
    new.setdefault(bone, []).append(c)

# ---------- waistband: 28 segs, elliptical, outer 3.45/2.45, h 0.52 ----------
N = 28
for k in range(N):
    phi = 2*math.pi*k/N
    # centerline ellipse (outer - thickness/2)
    rx = 3.45 - 0.17; rz = 2.45 - 0.17
    cx = x0 + rx*SIN(phi); cz = -rz*COS(phi)
    center = [cx, (23.42+23.92)/2, cz]
    t = [COS(phi), 0.0, SIN(phi)]
    R = frame(t, [0,1,0])
    add("Skirt", cube("Skirt", center, [0.95, 0.52, 0.34], R, C_MID)[1])

# ---------- peplum: 32 segs, top outer 3.42/2.44 y23.45 -> bottom outer 4.55/3.35 y22.05 ----------
N = 32
for k in range(N):
    phi = 2*math.pi*k/N
    bone, c = panel(phi, 3.42-0.13, 2.44-0.13, 23.45, 4.55-0.13, 22.05, 1.16, 0.26, C_BLACK, "Skirt", ext_top=0.30)
    add(bone, c)

# ---------- peplum ruffle: 32 cards at peplum hem ----------
for k in range(N):
    phi = 2*math.pi*k/N
    bone = quad_bone(phi)
    # top outer 4.55/3.35 at y22.05, bottom outer 4.95/3.65 at y21.45
    tx, tz = ell(4.55, 3.35, phi); bx, bz = ell(4.95, 3.65, phi)
    Ptop = [x0+tx, 22.05, tz]; Pbot=[x0+bx, 21.45, bz]
    mid = [(Ptop[i]+Pbot[i])/2 for i in range(3)]
    u = [Ptop[i]-Pbot[i] for i in range(3)]
    L0 = math.sqrt(sum(v*v for v in u)); u=[v/L0 for v in u]
    L = L0 + 0.06
    t = [COS(phi), 0, SIN(phi)]
    R = frame(t, u)
    add(bone, cube(bone, mid, [1.16, L, 0.20], R, C_DARK)[1])

# ---------- black bell: 36 tilted panels ----------
N = 36
for k in range(N):
    phi = 2*math.pi*k/N
    bone, c = panel(phi, 3.40-0.14, 2.42-0.14, Y_TOP, radius_bot(phi)-0.14, y_hem_bell(phi), 1.34, 0.28, C_BLACK, "Skirt", ext_top=0.35)
    add(bone, c)

# ---------- hem ruffle: 36 cards ----------
for k in range(N):
    phi = 2*math.pi*k/N
    bone = quad_bone(phi)
    r0 = radius_bot(phi)
    Ptop = [x0 + r0*SIN(phi), y_hem_bell(phi)+0.06, -r0*COS(phi)]
    r1 = r0 + 0.34
    Pbot = [x0 + r1*SIN(phi), y_hem_bell(phi)-0.62, -r1*COS(phi)]
    mid = [(Ptop[i]+Pbot[i])/2 for i in range(3)]
    u = [Ptop[i]-Pbot[i] for i in range(3)]
    L0 = math.sqrt(sum(v*v for v in u)); u=[v/L0 for v in u]
    t = [COS(phi), 0, SIN(phi)]
    R = frame(t, u)
    add(bone, cube(bone, mid, [1.30, L0+0.06, 0.22], R, C_DARK)[1])

# ---------- blue lining: 32 panels ----------
N = 32
for k in range(N):
    phi = 2*math.pi*k/N
    # top centerline 3.00/2.00 ; bottom centerline = black centerline - 0.40
    r_bot = radius_bot(phi) - 0.14 - 0.40
    bone, c = panel(phi, 3.00, 2.00, Y_TOP, r_bot, y_hem_blue(phi), 1.30, 0.26, C_BLUE, "Skirt", ext_top=0.30)
    add(bone, c)

# ---------- white edge: 32 vertical bands ----------
for k in range(N):
    phi = 2*math.pi*k/N
    r_bot = radius_bot(phi) - 0.14 - 0.40 + 0.02
    yb = y_hem_blue(phi)
    bone, c = vband(phi, r_bot, r_bot, yb+0.02, r_bot, yb-0.28, 1.30, 0.30, C_WHITE, "Skirt", ext_top=0.0)
    add(bone, c)

# ---------- write ----------
DRY = bool(os.environ.get("V7B_DRY"))
if DRY:
    for k, v in new.items():
        print("DRY", k, len(v))
    tot = sum(len(v) for v in new.values())
    print("DRY new cubes", tot, "final", 1130 - 195 + tot)
    raise SystemExit
shutil.copyfile(P, BAK)
OUT = os.environ.get("V7B_OUT", P)
d = json.load(open(P, encoding="utf-8"))
g = d["minecraft:geometry"][0]
bones = g["bones"]
names = {"Skirt","RightSkirt","LeftSkirt","FrontSkirt","BackSkirt"}
for b in bones:
    if b["name"] in names:
        b["cubes"] = []
        if b["name"] in new:
            b["cubes"] = new[b["name"]]
now = sum(len(b.get("cubes", [])) for b in bones)
print("total cubes now:", now)
for b in bones:
    if b["name"] in names:
        print(b["name"], len(b["cubes"]))
json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("written", OUT, os.path.getsize(OUT))



