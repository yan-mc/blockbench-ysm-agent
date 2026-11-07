"""Emit compact patch ops to fan the bangs strands (z-rotation around each strand root)
and add slight depth offsets. Reads the saved pack model."""
import json

path = r"F:\Deepseek_harness\blockbench\models\deepseek-fish\sakiko-melodia\models\main.json"
data = json.load(open(path, encoding="utf-8"))
geo = data["minecraft:geometry"][0]
bones = {b["name"]: b for b in geo["bones"]}

# names are duplicated; identify bangs by size/position
bangs = bones["Bangs"]["cubes"]
longs = [c for c in bangs if abs(c["size"][0] - 0.44) < 0.01]
inner = [c for c in bangs if abs(c["size"][0] - 0.58) < 0.01]
longs.sort(key=lambda c: c["origin"][0])
inner.sort(key=lambda c: c["origin"][0])
print("long strands:", len(longs), "inner:", len(inner))

# rotations alternate; angle grows toward the sides
ops = []
for i, c in enumerate(longs):
    ox, oy, oz = c["origin"]
    sx, sy, sz = c["size"]
    cx = ox + sx / 2
    top = oy + sy
    mid = (i - (len(longs) - 1) / 2) / ((len(longs) - 1) / 2)   # -1 .. 1
    ang = (2.5 + 2.5 * abs(mid)) * (1 if i % 2 == 0 else -1)
    ang += 1.0 * mid
    dz = -0.03 if i % 2 == 0 else 0.02
    ops.append({
        "op": "update_cube", "id": None, "name": c["name"],
        "origin": [round(ox, 3), round(oy, 3), round(oz + dz, 3)],
        "rotation": [0, 0, round(ang, 1)],
        "pivot": [round(cx, 3), round(top, 3), round(oz + sz / 2, 3)],
    })
for c in inner:
    ox, oy, oz = c["origin"]
    sx, sy, sz = c["size"]
    ops.append({"op": "update_cube", "name": c["name"], "origin": [0, 0, 0]})

print(json.dumps(longs[:3], indent=1)[:800])
