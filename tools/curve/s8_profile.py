#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全语料「中线连通剖面」：每个 y 切片只取含 x=0 的连通区间 → 躯干/胯/腿的真实轮廓。
排除头发/披风/武器/翅膀/尾巴（外挂物），可选是否含裙。
输出 out_profile.json：每模型宽/深剖面 + 关键地标。
"""
import json
import math
import sys
from collections import defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
STEP = 0.5
EXCL = H.RE_HAIR, H.RE_CAPE, H.RE_WEAPON


def excluded(bone_name):
    low = bone_name.lower()
    return any(r.search(low) for r in EXCL)


def profile(n, include_skirt=True, include_arms=True):
    cs = []
    for c in F[n]["cubes"]:
        low = c["b"].lower()
        if excluded(c["b"]):
            continue
        if not include_skirt and H.is_skirt(c["b"]):
            continue
        if not include_arms and H.RE_ARM.search(low):
            continue
        cs.append(c)
    if not cs:
        return None
    slices = defaultdict(list)
    for c in cs:
        b0 = int(math.floor(c["bb"][1] / STEP))
        b1 = max(b0 + 1, int(math.ceil(c["bb"][4] / STEP)))
        rec = (c["bb"][0], c["bb"][3], c["bb"][2], c["bb"][5], c["b"])
        for k in range(b0, b1):
            slices[k].append(rec)
    out = {}
    for k, ivs in slices.items():
        ivs.sort()
        # 合并 x 区间
        runs = []
        for x0, x1, z0, z1, bn in ivs:
            if runs and x0 <= runs[-1][1] + 1e-6:
                runs[-1][1] = max(runs[-1][1], x1)
                runs[-1][2].add(bn)
            else:
                runs.append([x0, x1, {bn}])
        # 取含 x=0 的区间（或最接近 0 的）
        best = None
        for r in runs:
            if r[0] <= 0 <= r[1]:
                if best is None or (r[1] - r[0]) > (best[1] - best[0]):
                    best = r
        if best is None:
            best = min(runs, key=lambda r: min(abs(r[0]), abs(r[1])))
        zs = [iv for iv in ivs if iv[0] >= best[0] - 1e-6 and iv[1] <= best[1] + 1e-6]
        z0 = min(iv[2] for iv in zs)
        z1 = max(iv[3] for iv in zs)
        out[k * STEP] = {"w": best[1] - best[0], "x0": best[0], "x1": best[1],
                         "d": z1 - z0, "z0": z0, "z1": z1,
                         "bones": sorted(best[2])}
    return out


def head_metrics(n):
    """头（不含头发）的宽/高，以及头顶 y。"""
    best = None
    for b in F[n]["bones"]:
        low = b["n"].lower()
        if not b["bb"]:
            continue
        if low in ("head", "allhead", "headbase"):
            if best is None or (b["bb"][4] - b["bb"][1]) > (best[1][4] - best[1][1]):
                best = (b["n"], b["bb"])
    if not best:
        return None
    bb = best[1]
    return {"bone": best[0], "w": bb[3] - bb[0], "h": bb[4] - bb[1], "top": bb[4], "bot": bb[1]}


def pivots(n):
    d = {}
    for b in F[n]["bones"]:
        low = b["n"].lower()
        if low in ("leftleg", "rightleg") and "y" not in d:
            d["leg_y"] = b["pivot"][1]
            d["leg_x"] = abs(b["pivot"][0])
        if low in ("leftarm", "rightarm") and "arm_y" not in d:
            d["arm_y"] = b["pivot"][1]
            d["arm_x"] = abs(b["pivot"][0])
        if low in ("leftlowerleg",) and "knee_y" not in d:
            d["knee_y"] = b["pivot"][1]
        if low in ("leftfoot",) and "ankle_y" not in d:
            d["ankle_y"] = b["pivot"][1]
        if low in ("neck",) and "neck_y" not in d:
            d["neck_y"] = b["pivot"][1]
        if low in ("leftlowerarm",) and "elbow_y" not in d:
            d["elbow_y"] = b["pivot"][1]
    return d


def foot_bottom(n):
    ys = []
    for b in F[n]["bones"]:
        if b["bb"] and H.RE_FOOT.search(b["n"].lower()):
            ys.append(b["bb"][1])
    return min(ys) if ys else None


res = {}
for n in sorted(F):
    p_all = profile(n, include_skirt=True)
    p_body = profile(n, include_skirt=False)
    if not p_all or len(p_all) < 20:
        continue
    hm = head_metrics(n)
    fb = foot_bottom(n)
    pv = pivots(n)
    if not hm or fb is None:
        continue
    ys = sorted(p_all)
    res[n] = {
        "profile": {str(k): v for k, v in p_all.items()},
        "profile_body": {str(k): v for k, v in (p_body or {}).items()},
        "head": hm, "foot_bottom": fb, "pivots": pv,
        "y_top": max(ys), "y_bot": min(ys),
        "cubes": F[n]["n_cubes"], "bones": F[n]["n_bones"],
    }

with open(r"F:\Deepseek_harness\blockbench\tools\curve\out_profile.json", "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False)
print("models profiled:", len(res))
print(json.dumps(res[sorted(res)[0]]["head"], ensure_ascii=False))
print(json.dumps(res[sorted(res)[0]]["pivots"], ensure_ascii=False))
