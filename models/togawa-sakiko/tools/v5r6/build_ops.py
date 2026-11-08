import json, math, copy, os

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
PACK = ROOT + r"\pack"
src = json.load(open(PACK + r"\models\main.json", encoding="utf-8"))
doc = copy.deepcopy(src)
geo = doc["minecraft:geometry"][0]
bones = {b["name"]: b for b in geo["bones"]}

# ---- A: remove cape cubes ----
for bn in ("Cape", "CapeLow"):
    n = len(bones[bn].get("cubes", []))
    bones[bn]["cubes"] = []
    print("cleared", bn, n)

BLACK = {"a": (206, 14), "b": (85, 229), "hi": (53, 229), "lo": (238, 14)}


def panel(theta, R, y0, H, W, T, col):
    t = math.radians(theta)
    cx, cz = R * math.cos(t), R * math.sin(t)
    origin = [round(cx - W / 2, 4), round(y0, 4), round(cz - T / 2, 4)]
    rot = [0, round((270 - theta) % 360, 2), 0]
    uv = col
    faces = {}
    sizes = {}
    for f in ("north", "east", "south", "west"):
        faces[f] = [uv[0], uv[1]]
        sizes[f] = [16, 16]
    faces["up"] = [53, 229]
    sizes["up"] = [16, 16]
    faces["down"] = [206, 14]
    sizes["down"] = [16, 16]
    return {
        "origin": origin,
        "size": [round(W, 4), round(H, 4), round(T, 4)],
        "rotation": rot,
        "uv": {"mode": "faces", "faces": faces, "sizes": sizes},
    }


new = []
# upper bell petals (hair-covered upper back, smooths taper) y 19.2-22.8
for i, (th, w, col, off) in enumerate([(62, 3.0, BLACK["a"], 0.0), (90, 3.1, BLACK["b"], 0.06), (118, 3.0, BLACK["a"], 0.0)]):
    new.append(panel(th, 4.55, 19.15 + off, 3.65 - off, w, 0.5, col))
# mid-hem continuous bell band y 15.15-17.85 : covers blue rim + gap under ruffle chips
for th, w, col, off in [(52, 3.3, BLACK["a"], 0.0), (90, 3.3, BLACK["b"], 0.05), (128, 3.3, BLACK["a"], 0.0)]:
    new.append(panel(th, 5.02, 15.15 + off, 2.7 - off, w, 0.44, col))
# hem frill y 14.35-15.75, slightly flared, scalloped bottom
for th, w, col, off, yaw in [(60, 3.1, BLACK["a"], 0.0, 5), (90, 3.15, BLACK["hi"], 0.14, -7), (120, 3.1, BLACK["b"], 0.0, 5)]:
    c = panel(th, 5.24, 14.35 + off, 1.45, w, 0.36, col)
    c["rotation"] = [0, round((270 - th + yaw) % 360, 2), 0]
    new.append(c)

for c in new:
    c.pop("uv", None)  # will be attached in ops
print("new cubes", len(new))
for c in new:
    print(c["origin"], c["size"], c["rotation"])

# ---- preview write to temp json (add raw uv faces like existing format) ----
def to_raw(c):
    o = dict(c)
    uvm = o["uv"] if isinstance(o.get("uv"), dict) and "faces" in o["uv"] else None
    return o

for c in new:
    faces = {}
    for f, uv in c["uvfaces"].items() if "uvfaces" in c else []:
        pass

# raw cubes: existing format per-face dict uv {face:{uv:[x,y],uv_size:[w,h]}}
raw_new = []
for i, c in enumerate(new):
    faces = {
        f: {"uv": [c["facesv"][f][0], c["facesv"][f][1]], "uv_size": [16, 16]}
        for f in ("north", "east", "south", "west", "up", "down")
    }
    raw_new.append({"origin": c["origin"], "size": c["size"], "rotation": c["rotation"], "uv": faces})
