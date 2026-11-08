import json, math

W = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
d = json.load(open(W + r"\checkpoints\r0025.bbmodel", encoding="utf-8"))
els = {e["uuid"]: e for e in d["elements"]}
groups = {g["uuid"]: g for g in d["groups"]}


def find_node(gid):
    tgt = None

    def walk(node):
        nonlocal tgt
        if isinstance(node, dict):
            if node.get("uuid") == gid:
                tgt = node
            for c in node.get("children", []):
                walk(c)
        elif isinstance(node, list):
            for c in node:
                walk(c)

    walk(d["outliner"])
    return tgt


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


head = find_node("2fb5ab7b-4ef6-ee16-e8be-d325b6b0ea05")
direct = [c for c in head["children"] if isinstance(c, str)]
print("direct children cubes:", len(direct))
xs = []; ys = []; zs = []
for u in direct:
    e = els[u]
    xs += [e["from"][0], e["to"][0]]
    ys += [e["from"][1], e["to"][1]]
    zs += [e["from"][2], e["to"][2]]
    print("head cube", e["name"], e["from"], e["to"], e.get("rotation"))
print("HEAD bounds x", min(xs), max(xs), "y", min(ys), max(ys), "z", min(zs), max(zs))

cubes = json.load(open(W + r"\artifacts\v7g_haircap_dump.json"))
print("== HairCap radial profile (max y per radius band, using cube corners)")
prof = {}
for c in cubes:
    f, t = c["f"], c["t"]
    for px in (f[0], t[0]):
        for pz in (f[2], t[2]):
            r = math.hypot(px, pz)
            b = round(r * 2) / 2
            prof[b] = max(prof.get(b, -99), t[1])
for k in sorted(prof):
    print("r=%4.1f ymax=%6.2f" % (k, prof[k]))
