#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第二遍：抽取每个模型的骨骼/方块几何事实，缓存为 out_facts.json。

记录（世界空间，已按父链累积旋转）：
  bones: name,parent,depth,pivot,rot,cube_count,bb(x0,y0,z0,x1,y1,z1)
  cubes: bone,origin,size,rot,pivot,rotated,center(world),bb(world),dims(min,mid,max)
"""
import json
import sys

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import ysm_lib as L


def r(x, n=2):
    return round(float(x), n)


def main():
    out = {}
    for name in L.all_models():
        m = L.load_model(name)
        bones = []
        cubes = []
        for n in m.order:
            b = m.bones[n]
            bb = m.bone_cube_bone_aabb(n)
            bones.append({
                "n": n, "p": b.parent, "rot": [r(x) for x in b.rotation],
                "pivot": [r(x) for x in b.pivot],
                "cc": len(b.cubes),
                "bb": [r(x) for x in bb] if bb else None,
                "kids": b.children,
            })
            for c in b.cubes:
                a = c.aabb_world(b.mat)
                cx = (a[0] + a[3]) / 2.0
                cy = (a[1] + a[4]) / 2.0
                cz = (a[2] + a[5]) / 2.0
                cubes.append({
                    "b": n,
                    "o": [r(x) for x in c.origin],
                    "s": [r(x) for x in c.size],
                    "r": [r(x) for x in c.rotation],
                    "rot": c.has_rot,
                    "c": [r(cx), r(cy), r(cz)],
                    "bb": [r(x) for x in a],
                    "infl": c.inflate,
                })
        out[name] = {
            "desc": m.desc,
            "bones": bones,
            "cubes": cubes,
            "n_bones": len(m.bones),
            "n_cubes": m.total_cubes(),
        }
        print(name, len(bones), m.total_cubes())
    with open(r"F:\Deepseek_harness\blockbench\tools\curve\out_facts.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
