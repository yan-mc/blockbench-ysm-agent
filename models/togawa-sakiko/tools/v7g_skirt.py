import json

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


for gname in ["FrontSkirt", "LeftSkirt", "Skirt"]:
    g = [x for x in d["groups"] if x.get("name") == gname][0]
    print("GROUP", gname, "origin", g.get("origin"), "rotation", g.get("rotation"))
    kids = collect(find_node(g["uuid"]))
    shown = 0
    for u in kids:
        e = els[u]
        rot = e.get("rotation")
        if rot and any(abs(v) > 0.01 for v in rot):
            print("  ", e["from"], e["to"], "rot", rot, "origin", e.get("origin"))
            shown += 1
            if shown >= 6:
                break
    print("  total", len(kids))
