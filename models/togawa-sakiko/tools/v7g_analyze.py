import json, math, sys

W = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
d = json.load(open(W + r"\checkpoints\r0025.bbmodel", encoding="utf-8"))
els = {e["uuid"]: e for e in d["elements"]}
groups = {g["uuid"]: g for g in d["groups"]}


def collect(node):
    out = []
    if isinstance(node, str):
        if node in groups:
            out += collect({"uuid": node, "children": groups[node].get("children", [])})
        elif node in els:
            out.append(node)
        return out
    if isinstance(node, dict):
        u = node.get("uuid")
        if u in groups:
            for c in node.get("children", []):
                out += collect(c)
        elif u in els:
            out.append(u)
        return out
    if isinstance(node, list):
        for c in node:
            out += collect(c)
    return out


def find_group(name, gid=None):
    tgt = None

    def walk(node):
        nonlocal tgt
        if isinstance(node, dict):
            u = node.get("uuid")
            if gid and u == gid:
                tgt = node
            for c in node.get("children", []):
                walk(c)
        elif isinstance(node, list):
            for c in node:
                walk(c)

    walk(d["outliner"])
    return tgt


head = find_group("Head", "2fb5ab7b-4ef6-ee16-e8be-d325b6b0ea05")
hkids = collect(head)
xs = []; ys = []; zs = []
for k in hkids:
    e = els[k]
    xs += [e["from"][0], e["to"][0]]
    ys += [e["from"][1], e["to"][1]]
    zs += [e["from"][2], e["to"][2]]
print("Head cubes", len(hkids), "x", min(xs), max(xs), "y", min(ys), max(ys), "z", min(zs), max(zs))

cubes = json.load(open(W + r"\artifacts\v7g_haircap_dump.json"))
for band in [(40.5, 99), (39.0, 40.5), (32.0, 39.0)]:
    top = [c for c in cubes if band[0] <= (c["f"][1] + c["t"][1]) / 2 < band[1]]
    print("== band", band, "count", len(top))
    if band[0] < 40.5:
        continue
    for c in sorted(top, key=lambda c: math.hypot((c["f"][0] + c["t"][0]) / 2, (c["f"][2] + c["t"][2]) / 2)):
        cx = (c["f"][0] + c["t"][0]) / 2
        cy = (c["f"][1] + c["t"][1]) / 2
        cz = (c["f"][2] + c["t"][2]) / 2
        r = math.hypot(cx, cz)
        ang = math.degrees(math.atan2(cz, cx)) % 360
        print("r=%5.2f ang=%6.1f c=(%5.2f,%5.2f,%5.2f) size=(%4.2f,%4.2f,%4.2f) rot=%s" % (r, ang, cx, cy, cz, c["size"][0], c["size"][1], c["size"][2], c["rot"]))
