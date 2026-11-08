import json, math

W = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
d = json.load(open(W + r"\checkpoints\r0025.bbmodel", encoding="utf-8"))
els = {e["uuid"]: e for e in d["elements"]}
groups = {g["uuid"]: g for g in d["groups"]}
byname = {g["name"]: g for g in d["groups"] if g["name"] not in [x["name"] for x in []]}


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
            out += collect(find_node(node))
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


for gname in ["HairCap", "front_h1", "corner_h1", "HairBack", "TwinTail_L", "hl_side", "Ribbon", "HairBow_R"]:
    g = byname[gname]
    kids = collect(find_node(g["uuid"]))
    xs = []; ys = []; zs = []
    for u in kids:
        e = els[u]
        xs += [e["from"][0], e["to"][0]]
        ys += [e["from"][1], e["to"][1]]
        zs += [e["from"][2], e["to"][2]]
    if kids:
        print("%-10s n=%3d x[%6.2f,%6.2f] y[%6.2f,%6.2f] z[%6.2f,%6.2f]" % (gname, len(kids), min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))

g = byname["front_h1"]
kids = collect(find_node(g["uuid"]))
tops = sorted(((els[u]["to"][1], els[u]["from"], els[u]["to"], els[u].get("rotation")) for u in kids), key=lambda x: -x[0])[:10]
print("front_h1 highest:")
for a, b, c, r in tops:
    print(" top", round(a, 2), b, c, r)
