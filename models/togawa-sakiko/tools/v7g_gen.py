import json, math

W = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
cubes = json.load(open(W + r"\artifacts\v7g_haircap_dump.json"))

delete_ids = [c["uuid"] for c in cubes if (c["f"][1] + c["t"][1]) / 2 >= 40.5]

rings = [
    # N, R, L, T, tilt, topMid, u, phase
    (12, 1.70, 1.20, 0.30, 7.0, 42.34, 86, 0.0),
    (16, 2.40, 1.35, 0.30, 12.0, 42.04, 86, 11.25),
    (20, 3.20, 1.40, 0.32, 15.0, 41.60, 86, 9.0),
    (24, 3.85, 1.75, 0.32, 15.0, 41.16, 70, 7.5),
]


def add_op(origin, size, rot, pivot, u, name="HairCap"):
    op = {
        "op": "add_cube", "bone": "HairCap", "name": name,
        "origin": [round(v, 2) for v in origin],
        "size": [round(v, 2) for v in size],
        "rotation": [round(v, 2) for v in rot],
        "pivot": [round(v, 2) for v in pivot],
        "uv": {"mode": "box", "uv": [u, 246]},
    }
    if all(abs(v) < 1e-9 for v in rot):
        op.pop("rotation")
    return op


ops = []
test = []  # (cx,cz, L, Wd, thetaRad, tiltDeg)
for N, R, L, T, tilt, topmid, u, phase in rings:
    Wd = 2 * math.pi * R / N * 1.30
    for i in range(N):
        ang = phase + i * 360.0 / N
        rad = math.radians(ang)
        x = R * math.cos(rad)
        z = R * math.sin(rad)
        yc = topmid - T / 2 + (i % 2) * 0.02
        ops.append(add_op([x - L / 2, yc - T / 2, z - Wd / 2], [L, T, Wd], [0, -ang, -tilt], [x, yc, z], u))
        test.append((x, z, L * math.cos(math.radians(tilt)), Wd, rad))

for i in (-1.5, -0.5, 0.5, 1.5):
    for j in (-1.5, -0.5, 0.5, 1.5):
        ops.append(add_op([i - 0.5, 42.15, j - 0.5], [1, 0.30, 1], [0, 0, 0], [i, 42.30, j], 86))
for i in (-0.5, 0.5):
    for j in (-0.5, 0.5):
        ops.append(add_op([i - 0.5, 42.35, j - 0.5], [1, 0.30, 1], [0, 0, 0], [i, 42.50, j], 96))

NC, RC, LC, HC = 24, 3.75, 0.50, 0.85
WdC = 2 * math.pi * RC / NC * 1.26
for i in range(NC):
    ang = i * 360.0 / NC + 7.5
    rad = math.radians(ang)
    x = RC * math.cos(rad)
    z = RC * math.sin(rad)
    yc = 40.425
    ops.append(add_op([x - LC / 2, yc - HC / 2, z - WdC / 2], [LC, HC, WdC], [0, -ang, -6.0], [x, yc, z], 54))

P = 1.6
for i in range(-2, 3):
    for j in range(-2, 3):
        if abs(i) == 2 and abs(j) == 2:
            continue
        x, z = i * P, j * P
        ops.append(add_op([x - P / 2, 40.29, z - P / 2], [P, 0.26, P], [0, 0, 0], [x, 40.42, z], 54))
for i in range(-1, 2):
    for j in range(-1, 2):
        x, z = i * P, j * P
        ops.append(add_op([x - P / 2, 40.67, z - P / 2], [P, 0.26, P], [0, 0, 0], [x, 40.80, z], 70))

print("delete", len(delete_ids), "add", len(ops))
json.dump({"ops": [{"op": "delete", "refs": [{"kind": "cube", "id": u} for u in delete_ids]}]},
          open(W + r"\artifacts\v7g_delete_ops.json", "w"), separators=(",", ":"))
json.dump({"ops": ops}, open(W + r"\artifacts\v7g_add_ops.json", "w"), separators=(",", ":"))


def top_covered(px, pz):
    # core
    if abs(px) <= 2.0 and abs(pz) <= 2.0:
        return True
    for cx, cz, Lp, Wd, rad in test:
        dx = px - cx
        dz = pz - cz
        # radial axis = (cos, sin), tangential = (-sin, cos)
        v = dx * math.cos(rad) + dz * math.sin(rad)
        u = -dx * math.sin(rad) + dz * math.cos(rad)
        if abs(v) <= Lp / 2 and abs(u) <= Wd / 2:
            return True
    return False


holes = []
step = 0.05
for i in range(-100, 101):
    for j in range(-100, 101):
        px, pz = i * step, j * step
        r = math.hypot(px, pz)
        if r <= 4.6 and not top_covered(px, pz):
            holes.append((round(px, 2), round(pz, 2)))
print("top-view uncovered sample points inside r<=4.6:", len(holes))
if holes:
    print("sample:", holes[:20])

