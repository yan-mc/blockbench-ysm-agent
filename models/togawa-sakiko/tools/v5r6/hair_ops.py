"""Build update ops that taper/shorten lower back hair (HairBack) using checkpoint uuids."""
import json

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
d = json.load(open(ROOT + r"\checkpoints\r0018.bbmodel", encoding="utf-8"))
els = {e["uuid"]: e for e in d["elements"] if e.get("type") == "cube"}
groups = {g["uuid"]: g for g in d["groups"]}
target = [g["uuid"] for g in d["groups"] if g.get("name") == "HairBack"][0]

found = []


def walk(node):
    if isinstance(node, dict):
        if node.get("uuid") == target:
            found.append(node)
        for c in node.get("children", []):
            walk(c)


for n in d["outliner"]:
    walk(n)

out = []


def collect(node):
    if isinstance(node, str):
        if node in els and node not in out:
            out.append(node)
        return
    u = node.get("uuid")
    if u in els and u not in out:
        out.append(u)
    for c in node.get("children", []):
        collect(c)


collect(found[0])
print("HairBack cubes", len(out))
rows = []
for u in out:
    c = els[u]
    frm, to = c["from"], c["to"]
    rows.append({"uuid": u, "from": frm, "to": to, "rot": c.get("rotation") or [0, 0, 0],
                 "pivot": c.get("origin") or [0, 0, 0]})

low = sorted([r for r in rows if r["to"][1] < 22.0], key=lambda r: r["from"][1])
print("cubes top<22:", len(low))
for r in low:
    print(f" {r['uuid'][:8]} x[{r['from'][0]:6.2f},{r['to'][0]:6.2f}] y[{r['from'][1]:6.2f},{r['to'][1]:6.2f}] z[{r['from'][2]:5.2f},{r['to'][2]:5.2f}] rot={r['rot']}")


def find(x0, y0, z0, tol=0.05):
    hits = [r for r in rows if abs(r["from"][0] - x0) < tol and abs(r["from"][1] - y0) < tol and abs(r["from"][2] - z0) < tol]
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
    frm = [round(r["from"][0] + dx, 4), round(r["from"][1] + dy, 4), round(r["from"][2], 4)]
    size = [round(r["to"][0] - r["from"][0], 4), round(r["to"][1] - r["from"][1], 4),
            round(r["to"][2] - r["from"][2], 4)]
    pivot = [round(frm[0] + size[0] / 2, 4), round(frm[1] + size[1] / 2, 4), round(frm[2] + size[2] / 2, 4)]
    ops.append({"op": "update_cube", "cube_id": r["uuid"], "origin": frm, "size": size,
                "rotation": [round(v, 4) for v in r["rot"]], "pivot": pivot})
    print("plan", r["uuid"][:8], "y", r["from"][1], "->", frm[1], " x", r["from"][0], "->", frm[0])

json.dump(ops, open(ROOT + r"\artifacts\v5\r6\hair_ops.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ops", len(ops))
