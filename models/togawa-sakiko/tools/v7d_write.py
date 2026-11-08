# -*- coding: utf-8 -*-
"""Write the v7d hair into pack/models/main.json (scripted route, avoids inlining
400+ ops through the MCP tool).

Conventions verified against the live project:
  * main.json x is MIRRORED relative to the Blockbench model (LeftArm pivot
    file +3.4 vs editor -3.4), so editor cubes are written as x -> -x,
    euler (a,b,c) -> (a,-b,-c), pivot -> mirrored.
  * cube rotation arrays are the ZYX decompositions the v7c skirt already uses.
"""
import json, os, shutil, sys, io

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
MAIN = os.path.join(ROOT, "pack", "models", "main.json")
BAK = os.path.join(ROOT, "pack", "models", "main.v7c-bak.json")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import v7d_gen as G

DROP_BONES = ["Hair", "HairBack", "hl_side", "front_h1", "corner_h1", "HairCap"]


def ysm_cube(c):
    """Cube (editor space) -> YSM cube dict (file space, x mirrored)."""
    e = G.euler_xyz(c.R)
    ux, uy = c.uv
    faces = {}
    for f in ("north", "east", "south", "west", "up", "down"):
        faces[f] = {"uv": [int(ux), int(uy)], "uv_size": [3, 3]}
    out = {
        "origin": [round(-c.c[0] - c.size[0] / 2, 4), round(c.c[1] - c.size[1] / 2, 4),
                   round(c.c[2] - c.size[2] / 2, 4)],
        "size": [round(c.size[0], 4), round(c.size[1], 4), round(c.size[2], 4)],
        "pivot": [round(-c.c[0], 4), round(c.c[1], 4), round(c.c[2], 4)],
        "rotation": [round(e[0], 2), round(-e[1], 2), round(-e[2], 2)],
        "uv": faces,
    }
    if abs(e[0]) < 1e-9 and abs(e[1]) < 1e-9 and abs(e[2]) < 1e-9:
        out.pop("rotation")
    return out


def main():
    G.main()
    cubes = G.LAST_CUBES
    d = json.load(io.open(MAIN, encoding="utf-8"))
    g = d["minecraft:geometry"][0]
    bones = g["bones"]
    if not os.path.exists(BAK):
        shutil.copyfile(MAIN, BAK)

    by_bone = {}
    for c in cubes:
        by_bone.setdefault(c.bone, []).append(c)

    for b in bones:
        if b["name"] in DROP_BONES:
            b["cubes"] = []

    # (re)create HairCap right after Hair, removing any previous copy
    bones[:] = [b for b in bones if b["name"] != "HairCap"]
    idx = next(i for i, b in enumerate(bones) if b["name"] == "Hair")
    bones.insert(idx + 1, {"name": "HairCap", "parent": "Hair",
                           "pivot": [0, 37.0, 0], "cubes": []})

    for b in bones:
        if b["name"] in by_bone:
            b["cubes"] = [ysm_cube(c) for c in by_bone[b["name"]]]

    json.dump(d, io.open(MAIN, "w", encoding="utf-8"), ensure_ascii=False,
              separators=(",", ":"))
    tot = sum(len(b.get("cubes", [])) for b in bones)
    print("wrote", MAIN)
    print("bones", len(bones), "cubes", tot)
    for n in ["Hair", "HairCap", "HairBack", "hl_side", "front_h1", "corner_h1"]:
        b = next(x for x in bones if x["name"] == n)
        print("  %-10s %3d" % (n, len(b.get("cubes", []))))


if __name__ == "__main__":
    main()
