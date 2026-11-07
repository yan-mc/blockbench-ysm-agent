#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""结构法躯干链：从骨架拓扑找躯干骨（手臂/头的祖先 ∩ 非头非臂），
只用这些骨的“自身方块”量躯干轮廓，避免裙子/披风污染。
输出 out_chain.json
"""
import json
import math
import sys
from collections import defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
STEP = 0.25

ARM_NAMES = ("leftarm", "rightarm", "arm")
HEAD_NAMES = ("allhead", "head")


def bone_map(n):
    return {b["n"]: b for b in F[n]["bones"]}


def chain(n):
    """返回躯干链骨名集合（从根到胸，含骨盆），以及 arm/head/leg 起点。"""
    bm = bone_map(n)
    arm = next((b for b in bm if b.lower() in ("leftarm", "rightarm")), None)
    head = next((b for b in bm if b.lower() in ("allhead", "head")), None)
    leg = next((b for b in bm if b.lower() in ("leftleg", "rightleg")), None)
    if not (arm and head):
        return None
    out = set()
    # arm 的祖先链（不含 arm 自身）
    for tgt in (arm, head):
        cur = bm[tgt].get("p")
        seen = set()
        while cur in bm and cur not in seen:
            seen.add(cur)
            out.add(cur)
            cur = bm[cur].get("p")
    # 骨盆链：leg 的祖先直到与 out 相交
    if leg:
        cur = bm[leg].get("p")
        seen = set()
        while cur in bm and cur not in seen and cur not in out:
            seen.add(cur)
            out.add(cur)
            cur = bm[cur].get("p")
    out.discard(None)
    return {"bones": out, "arm": arm, "head": head, "leg": leg, "bm": bm}


def head_metrics(n, bm, head_name):
    """头（不含头发）：头骨自身方块 bbox。"""
    names = [head_name]
    b = bm.get(head_name)
    if b and b.get("p"):
        pass
    # 优先取名为 head 的骨（allhead 常为容器）
    cands = [x for x in bm if x.lower() in ("head", "allhead")]
    best = None
    for c in cands:
        bb = bm[c].get("bb")
        if not bb:
            continue
        h = bb[4] - bb[1]
        if best is None or h > best[1]:
            best = (c, h)
    if not best:
        return None
    bb = bm[best[0]]["bb"]
    return {"bone": best[0], "w": bb[3] - bb[0], "h": bb[4] - bb[1], "top": bb[4], "bot": bb[1]}


def profile_from_cubes(cubes, step=STEP):
    """含 x=0 的 x 区间合并 + 该区间 z 跨度。返回 {y: {...}}"""
    slices = defaultdict(list)
    for c in cubes:
        b0 = int(math.floor(c["bb"][1] / step))
        b1 = max(b0 + 1, int(math.ceil(c["bb"][4] / step)))
        rec = (c["bb"][0], c["bb"][3], c["bb"][2], c["bb"][5], c["b"])
        for k in range(b0, b1):
            slices[k].append(rec)
    out = {}
    for k, ivs in slices.items():
        ivs.sort()
        runs = []
        for x0, x1, z0, z1, bn in ivs:
            if runs and x0 <= runs[-1][1] + 1e-6:
                runs[-1][1] = max(runs[-1][1], x1)
                runs[-1][2].add(bn)
            else:
                runs.append([x0, x1, {bn}])
        cand = [r for r in runs if r[0] <= 0 <= r[1]]
        best = max(cand, key=lambda r: r[1] - r[0]) if cand else None
        if best is None:
            continue
        zs = [iv for iv in ivs if iv[0] >= best[0] - 1e-6 and iv[1] <= best[1] + 1e-6]
        out[k * step] = {"w": best[1] - best[0], "x0": best[0], "x1": best[1],
                         "d": max(iv[3] for iv in zs) - min(iv[2] for iv in zs),
                         "bones": sorted(best[2])}
    return out


def foot_bottom(n, bm):
    ys = [b["bb"][1] for b in bm.values() if b.get("bb") and H.RE_FOOT.search(b["n"].lower())]
    return min(ys) if ys else None


res = {}
for n in sorted(F):
    ch = chain(n)
    if not ch:
        continue
    bm, torso = ch["bm"], ch["bones"]
    hm = head_metrics(n, bm, ch["head"])
    fb = foot_bottom(n, bm)
    if not hm or fb is None:
        continue
    own = [c for c in F[n]["cubes"] if c["b"] in torso]
    if len(own) < 4:
        continue
    prof = profile_from_cubes(own)
    if len(prof) < 10:
        continue
    segs = []
    for bn in sorted(torso):
        b = bm[bn]
        if not b.get("bb"):
            continue
        cs = [c for c in F[n]["cubes"] if c["b"] == bn]
        if not cs:
            continue
        segs.append({
            "name": bn,
            "w": round(b["bb"][3] - b["bb"][0], 2),
            "y0": round(b["bb"][1], 2), "y1": round(b["bb"][4], 2),
            "n": len(cs),
            "rot": round(sum(1 for c in cs if c["rot"]) / len(cs), 3),
            "thick": round(min(min(c["s"]) for c in cs), 2),
        })
    segs.sort(key=lambda s: s["y0"])
    arm_y = bm[ch["arm"]]["pivot"][1]
    leg_y = bm[ch["leg"]]["pivot"][1] if ch["leg"] else None
    res[n] = {
        "head": hm, "foot_bottom": fb, "arm_y": arm_y, "leg_y": leg_y,
        "torso_bones": sorted(torso), "segs": segs,
        "profile": {str(k): v for k, v in prof.items()},
        "n_torso_cubes": len(own),
        "n_torso_bones": len([s for s in segs if s["n"] > 0]),
        "rot_frac": round(sum(1 for c in own if c["rot"]) / len(own), 3),
        "cubes": F[n]["n_cubes"],
    }

with open(r"F:\Deepseek_harness\blockbench\tools\curve\out_chain.json", "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False)
print("models with structural torso chain:", len(res))

n0 = "hi3_elysia__ae12017978c2"
if n0 in res:
    d = res[n0]
    print(n0, "torso_bones", d["torso_bones"], "n_torso_cubes", d["n_torso_cubes"],
          "rot", d["rot_frac"])
    for s in d["segs"]:
        print("   %-22s y=%6.2f..%6.2f w=%5.2f n=%-3d rot=%.2f thick=%.2f" %
              (s["name"], s["y0"], s["y1"], s["w"], s["n"], s["rot"], s["thick"]))
    for y in sorted(float(k) for k in d["profile"]):
        if 55 <= y <= 95:
            v = d["profile"][str(y)]
            print("   y=%5.1f w=%5.1f d=%5.1f %s" % (y, v["w"], v["d"], ",".join(v["bones"])[:34]))
