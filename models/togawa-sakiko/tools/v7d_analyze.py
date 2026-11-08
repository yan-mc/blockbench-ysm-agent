# -*- coding: utf-8 -*-
"""v7d hair analysis: read checkpoint bbmodel, map cubes to hair bones, report bbox,
palette, and scalp-coverage ray test."""
import json, math, sys, os

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
BBM = os.path.join(ROOT, "checkpoints", "r0006.bbmodel")

BONE_UUID = {
    "Head": "ee15d849-c1e9-9f28-6b9d-197fb7d1c87c",
    "Hair": "ebbd2a88-1990-26ea-802a-18edcec8f93c",
    "FLongHair": "ecf16dc4-ab69-3409-43c2-e6802696274b",
    "MLongHair": "ce18e130-46ed-6ac0-6209-157da820f8ff",
    "LongHair": "7ba89367-00be-ebaf-3149-aa5cbc9750c0",
    "HairBack": "f29069bb-568e-3faf-46e1-f2e62662ef70",
    "hl_side": "0f1db665-b7e4-6417-fc54-1a02c2495e2a",
    "front_h1": "d4fe7e84-5ba6-6660-7f1e-b97f99e898b4",
    "corner_h1": "78423a06-2cd9-a483-d5e5-b6c34314b590",
    "TwinTail_L": "883c24fa-607f-d2fd-1091-0dbd75c282a4",
    "TwinTail_R": "e5878921-72a6-89e9-1942-3498994b00e8",
    "Ribbon": "0d168010-d24e-dc73-b075-6102452f8569",
    "HairBow_R": "ef18b69c-56dc-ab96-80be-5537475c70ea",
}
UUID_BONE = {v: k for k, v in BONE_UUID.items()}


def load():
    d = json.load(open(BBM, encoding="utf-8"))
    els = {e["uuid"]: e for e in d["elements"] if e.get("type") == "cube"}
    owner = {}
    tree = {}

    def walk(node):
        if isinstance(node, str):
            return
        u = node.get("uuid")
        tree[u] = node
        for ch in node.get("children", []):
            if isinstance(ch, str):
                if ch in els and u in UUID_BONE:
                    owner[ch] = UUID_BONE[u]
            else:
                walk(ch)

    for n in d["outliner"]:
        walk(n)
    return d, els, owner, tree


def cube_geo(e):
    f = e["from"]; t = e["to"]
    o = [min(f[i], t[i]) for i in range(3)]
    s = [abs(t[i] - f[i]) for i in range(3)]
    return o, s


def main():
    d, els, owner, tree = load()
    from collections import defaultdict
    per = defaultdict(list)
    for u, b in owner.items():
        per[b].append(u)
    for b in BONE_UUID:
        us = per.get(b, [])
        if not us:
            continue
        xs = []; ys = []; zs = []
        for u in us:
            o, s = cube_geo(els[u])
            xs += [o[0], o[0] + s[0]]; ys += [o[1], o[1] + s[1]]; zs += [o[2], o[2] + s[2]]
        print("%-11s n=%3d  x[%6.2f,%6.2f] y[%6.2f,%6.2f] z[%6.2f,%6.2f]" % (
            b, len(us), min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)))
    total = sum(len(v) for v in per.values())
    print("hair-owned cubes:", total, "/", len(els))
    # sample one cube to verify coordinate space
    u0 = per["Hair"][0]
    e = els[u0]
    print("sample Hair cube", u0, "from", e["from"], "to", e["to"], "origin", e.get("origin"), "rotation", e.get("rotation"))


if __name__ == "__main__":
    main()
