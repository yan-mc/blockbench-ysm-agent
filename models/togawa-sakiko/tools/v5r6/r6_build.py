"""Build r6 back-skirt additions. Outputs preview model json + patch ops json."""
import json, math, copy, os

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
PACK = ROOT + r"\pack"
OUT = ROOT + r"\artifacts\v5\r6"
os.makedirs(OUT, exist_ok=True)

src = json.load(open(PACK + r"\models\main.json", encoding="utf-8"))
doc = copy.deepcopy(src)
bones = {b["name"]: b for b in doc["minecraft:geometry"][0]["bones"]}

# A: this preview also removes cape cubes
for bn in ("Cape", "CapeLow"):
    bones[bn]["cubes"] = []

SW = {"a": [206, 14], "b": [85, 229], "hi": [53, 229], "lo": [238, 14]}


def cube(theta, R, y0, H, W, T, col, yaw_off=0.0):
    t = math.radians(theta)
    cx, cz = R * math.cos(t), R * math.sin(t)
    origin = [round(cx - W / 2, 4), round(y0, 4), round(cz - T / 2, 4)]
    rot = [0, round((270 - theta + yaw_off) % 360, 2), 0]
    faces = {}
    for f in ("north", "east", "south", "west"):
        faces[f] = {"uv": list(SW[col]), "uv_size": [3, 3]}
    faces["up"] = {"uv": [53, 229], "uv_size": [3, 3]}
    faces["down"] = {"uv": [206, 14], "uv_size": [3, 3]}
    return {"origin": origin, "size": [round(W, 4), round(H, 4), round(T, 4)],
            "rotation": rot, "uv": faces}


new = []
# 1) upper bell petals: y 19.15-22.8 (visible through hair gaps / 3-4 views)
for th, w, col, off in [(62, 3.0, "a", 0.0), (90, 3.1, "b", 0.06), (118, 3.0, "a", 0.0)]:
    new.append(cube(th, 4.55, 19.15 + off, 3.65 - off, w, 0.5, col))
# 2) mid-hem continuous black bell band: y 15.15-17.85 (covers petticoat rim + gaps)
for th, w, col, off in [(52, 3.3, "a", 0.0), (90, 3.3, "b", 0.05), (128, 3.3, "a", 0.0)]:
    new.append(cube(th, 5.02, 15.15 + off, 2.7 - off, w, 0.44, col))
# 3) hem frill: y 14.35-15.8, flared, scalloped
for th, w, col, off, yaw in [(60, 3.1, "a", 0.0, 5), (90, 3.15, "hi", 0.14, -7), (120, 3.1, "b", 0.0, 5)]:
    new.append(cube(th, 5.24, 14.35 + off, 1.45, w, 0.36, col, yaw))

bones["BackSkirt"]["cubes"].extend(new)
json.dump(doc, open(OUT + r"\preview_main.json", "w", encoding="utf-8"), ensure_ascii=False)
print("preview cubes total", sum(len(b.get("cubes", [])) for b in doc["minecraft:geometry"][0]["bones"]))

# patch ops (add_cube with uv mode faces + sizes)
ops = []
for c in new:
    faces = {f: list(v["uv"]) for f, v in c["uv"].items()}
    sizes = {f: [3, 3] for f in c["uv"]}
    ops.append({"op": "add_cube", "bone": "BackSkirt",
                "origin": c["origin"], "size": c["size"], "rotation": c["rotation"],
                "uv": {"mode": "faces", "faces": faces, "sizes": sizes}})
json.dump(ops, open(OUT + r"\add_ops.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ops", len(ops))
for c in new:
    print(c["origin"], c["size"], c["rotation"], c["uv"]["south"]["uv"])
