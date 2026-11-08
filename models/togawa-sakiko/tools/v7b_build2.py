import json, math, shutil, os

P = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\models\main.json"
BAK = P + ".v7a-bak"
x0 = -0.15

def ell(rx, rz, phi):
    return (rx*math.sin(phi), -rz*math.cos(phi))

def euler_zyx(R):
    s = max(-1.0, min(1.0, -R[2][0])); b = math.asin(s)
    if abs(R[2][0]) < 0.999999:
        a = math.atan2(R[2][1], R[2][2]); c = math.atan2(R[1][0], R[0][0])
    elif R[2][0] >= 0:
        b = -math.pi/2; a = math.atan2(-R[0][1], -R[0][2]); c = 0.0
    else:
        b = math.pi/2; a = math.atan2(R[0][1], R[0][2]); c = 0.0
    return [math.degrees(a), math.degrees(b), math.degrees(c)]

def emit(bone, center, size, uv, ry_deg=0.0):
    # only Y rotation (safe under any euler order); center/size in Blockbench space
    mx = -(center[0] + size[0]/2)
    my = center[1] - size[1]/2
    mz = center[2] - size[2]/2
    return bone, {
        "origin": [round(mx,4), round(my,4), round(mz,4)],
        "size": [round(v,4) for v in size],
        "pivot": [round(-center[0],4), round(center[1],4), round(center[2],4)],
        "rotation": [0.0, round(-ry_deg,3), 0.0],
        "uv": uv,
    }

def ring(name, N, rx, rz, y0, y1, width, thick, uv, bone="Skirt", phi0=0.0):
    out = []
    for k in range(N):
        phi = 2*math.pi*k/N + phi0
        cx = x0 + rx*math.sin(phi); cz = -rz*math.cos(phi)
        ry = -math.degrees(phi)   # bb rotation about Y so width is tangential
        out.append(emit(bone, [cx, (y0+y1)/2, cz], [width, y1-y0, thick], uv, ry))
    return out

# ---- palette ----
C_BLACK = [200,18]; C_DARK=[226,18]; C_MID=[258,18]
C_BLUE = [178,226]; C_WHITE=[162,226]

def y_hem_bell(phi): return 14.10 + 1.50*math.cos(phi)
def y_hem_blue(phi): return 13.35 + 0.80*math.cos(phi)
def r_hem(phi): return 5.54 + 0.10*math.cos(phi) - 0.22*math.cos(2*phi)   # centerline hem radius

new = {}
def add(entries):
    for bone, c in entries:
        new.setdefault(bone, []).append(c)

# ---------- waistband: 28 segs ----------
add(ring("belt", 28, 3.28, 2.28, 23.42, 23.92, 0.96, 0.34, C_MID))

# ---------- peplum: two rings (outer tiers), split over 4 skirt bones ----------
def quad_bone(phi):
    d = math.degrees(phi) % 360
    if d <= 45 or d >= 315: return "FrontSkirt"
    if d < 135: return "RightSkirt"
    if d < 225: return "BackSkirt"
    return "LeftSkirt"
for tier,(rx,rz,y0,y1) in enumerate([(3.42,2.42,23.35,22.60),(4.05,2.95,22.55,21.95),(4.55,3.30,21.90,21.55)]):
    for k in range(28):
        phi = 2*math.pi*k/28
        b = quad_bone(phi)
        cx = x0 + rx*math.sin(phi); cz = -rz*math.cos(phi)
        add([emit(b, [cx,(y0+y1)/2,cz], [1.22, y1-y0, 0.26], C_BLACK if tier!=1 else C_DARK, -math.degrees(phi))])

# ---------- black bell: 4 vertical tiers x 36 ----------
Y_TOP = 23.55
RT = (3.26, 2.28)   # centerline top (outer 3.40/2.42)
BOUNDS = [0.0, 0.26, 0.53, 0.78, 1.0]
for ti in range(4):
    t0, t1 = BOUNDS[ti], BOUNDS[ti+1]
    for k in range(36):
        phi = 2*math.pi*k/36
        yh = y_hem_bell(phi); rh = r_hem(phi)
        y0 = Y_TOP - t0*(Y_TOP-yh); y1 = Y_TOP - t1*(Y_TOP-yh)
        top = y0 if ti == 0 else y0 + 0.35
        if ti == 0:
            r, rz = RT[0], RT[1]
        else:
            r = RT[0] + (rh - RT[0])*t1
            rz = RT[1] + (rh - RT[1])*t1
        cx = x0 + r*math.sin(phi); cz = -rz*math.cos(phi)
        add([emit("Skirt", [cx,(top+y1)/2,cz], [1.20, top-y1, 0.28], C_BLACK if ti%2==0 else C_DARK, -math.degrees(phi))])

# ---------- blue lining: 3 tiers x 32 ----------
BOUNDB = [0.0, 0.35, 0.70, 1.0]
for ti in range(3):
    t0,t1 = BOUNDB[ti], BOUNDB[ti+1]
    for k in range(32):
        phi = 2*math.pi*k/32
        yh = y_hem_blue(phi); ybh = y_hem_bell(phi)
        y0 = Y_TOP - t0*(Y_TOP-yh); y1 = Y_TOP - t1*(Y_TOP-yh)
        top = y0 if ti==0 else y0+0.30
        tb = min(1.0, (Y_TOP-y0)/(Y_TOP-ybh))
        r = RT[0] + (r_hem(phi)-RT[0])*tb - 0.45
        rz = RT[1] + (r_hem(phi)-RT[1])*tb - 0.45
        cx = x0 + r*math.sin(phi); cz = -rz*math.cos(phi)
        add([emit("Skirt", [cx,(top+y1)/2,cz], [1.22, top-y1, 0.26], C_BLUE, -math.degrees(phi))])

# ---------- white edge: 32 ----------
for k in range(32):
    phi = 2*math.pi*k/32
    yb = y_hem_blue(phi)
    rh = r_hem(phi)-0.45+0.02
    cx = x0 + rh*math.sin(phi); cz = -rh*math.cos(phi)
    add([emit("Skirt", [cx,(yb-0.13),cz], [1.22, 0.30, 0.30], C_WHITE, -math.degrees(phi))])

DRY = bool(os.environ.get("V7B_DRY"))
if DRY:
    for k,v in new.items(): print("DRY", k, len(v))
    tot=sum(len(v) for v in new.values()); print("DRY new", tot, "final", 1130-195+tot); raise SystemExit

shutil.copyfile(P, BAK)
OUT = os.environ.get("V7B_OUT", P)
d = json.load(open(P, encoding="utf-8"))
bones = d["minecraft:geometry"][0]["bones"]
names = {"Skirt","RightSkirt","LeftSkirt","FrontSkirt","BackSkirt"}
for b in bones:
    if b["name"] in names:
        b["cubes"] = new.get(b["name"], [])
print("total cubes now:", sum(len(b.get("cubes",[])) for b in bones))
for b in bones:
    if b["name"] in names: print(b["name"], len(b["cubes"]))
json.dump(d, open(OUT,"w",encoding="utf-8"), ensure_ascii=False, separators=(",",":"))
print("written", OUT, os.path.getsize(OUT))

