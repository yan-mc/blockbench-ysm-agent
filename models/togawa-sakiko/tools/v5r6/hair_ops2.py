"""Build update ops to taper lower back hair. Coordinates in main.json convention (tool get_element style)."""
import json

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
bmd = json.load(open(ROOT + r"\checkpoints\r0018.bbmodel", encoding="utf-8"))
main = json.load(open(ROOT + r"\pack\models\main.json", encoding="utf-8"))
els = {e["uuid"]: e for e in bmd["elements"] if e.get("type") == "cube"}
target = [g["uuid"] for g in bmd["groups"] if g.get("name") == "HairBack"][0]

found = []


def walk(n):
    if isinstance(n, dict):
        if n.get("uuid") == target:
            found.append(n)
        for c in n.get("children", []):
            walk(c)


for n in bmd["outliner"]:
    walk(n)
out = []


def collect(n):
    if isinstance(n, str):
        if n in els and n not in out:
            out.append(n)
        return
    u = n.get("uuid")
    if u in els and u not in out:
        out.append(u)
    for c in n.get("children", []):
        collect(c)


collect(found[0])
mb = [b for b in main["minecraft:geometry"][0]["bones"] if b["name"] == "HairBack"][0]["cubes"]
assert len(out) == len(mb), (len(out), len(mb))

rows = []
for i, (u, c) in enumerate(zip(out, mb)):
    o = c["origin"]; s = c["size"]
    rows.append({"uuid": u, "origin": o, "size": s, "rot": c.get("rotation") or [0, 0, 0],
                 "pivot": c.get("pivot") or [o[0] + s[0] / 2, o[1] + s[1] / 2, o[2] + s[2] / 2]})

# sanity: pivot is center in main.json?
bad = [r for r in rows if any(abs(r["pivot"][k] - (r["origin"][k] + r["size"][k] / 2)) > 1e-3 for k in range(3))]
print("pivot != center:", len(bad))

low = sorted([r for r in rows if r["origin"][1] + r["size"][1] < 22.0], key=lambda r: r["origin"][1])
print("cubes top<22:", len(low))


def find(x0, y0, z0, tol=0.05):
    hits = [r for r in rows if abs(r["origin"][0] - x0) < tol and abs(r["origin"][1] - y0) < tol and abs(r["origin"][2] - z0) < tol]
    assert len(hits) == 1, (x0, y0, z0, len(hits))
    return hits[0]


spec = [
    (-2.18, 15.60, 5.56, 2.6, 0.0),
    (3.02, 16.35, 5.18, 2.3, 0.0),
    (-2.09, 16.42, 5.27, 2.1, 0.0),
    (2.59, 17.17, 4.89, 1.7, 0.0),
    (-0.28, 18.04, 4.80, 1.3, 0.0),
    (-2.10, 18.71, 4.52, 1.1, 0.0),
    (-3.46, 18.75, 5.17, 1.3, 0.0),
    (-0.70, 18.86, 4.51, 1.1, 0.0),
    (-2.00, 19.53, 4.23, 0.9, 0.0),
    (-3.37, 19.57, 4.88, 1.0, 0.0),
    (4.63, 19.88, 5.33, 0.9, -0.9),
    (2.91, 20.29, 4.86, 0.7, 0.0),
    (-3.02, 20.22, 6.21, 0.8, 0.0),
    (2.28, 20.74, 5.90, 0.6, 0.0),
    (-4.95, 18.90, 5.60, 1.0, 1.2),
    (4.10, 18.90, 5.60, 1.0, -1.2),
    (-5.20, 19.60, 4.55, 0.8, 1.0),
    (4.30, 19.60, 4.55, 0.8, -1.0),
    (4.45, 20.13, 4.46, 0.6, -0.9),
    (-4.95, 20.60, 5.90, 0.5, 0.8),
    (4.10, 20.60, 5.90, 0.5, -0.8),
]

ops = []
for (x, y, z, dy, dx) in spec:
    r = find(x, y, z)
    o = [round(r["origin"][0] + dx, 4), round(r["origin"][1] + dy, 4), round(r["origin"][2], 4)]
    # rigid translation: pivot moves with the cube (rotation behaviour preserved)
    piv = [round(r["pivot"][0] + dx, 4), round(r["pivot"][1] + dy, 4), round(r["pivot"][2], 4)]
    ops.append({"op": "update_cube", "cube_id": r["uuid"], "origin": o,
                "size": [round(v, 4) for v in r["size"]],
                "rotation": [round(v, 4) for v in r["rot"]], "pivot": piv})
    print("plan", r["uuid"][:8], f"y {r['origin'][1]:.2f}->{o[1]:.2f}  x {r['origin'][0]:.2f}->{o[0]:.2f}")

json.dump(ops, open(ROOT + r"\artifacts\v5\r6\hair_ops.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ops", len(ops))
