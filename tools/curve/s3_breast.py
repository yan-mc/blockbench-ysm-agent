#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q1 胸：骨名分布、块数/尺寸/旋转、半球拟合、衣服版对比。"""
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
names = sorted(F.keys())

# ---------------------------------------------------------------- 1. 骨名清单
fam = Counter()
models_with = defaultdict(set)
cubes_with = Counter()
for n in names:
    for b in F[n]["bones"]:
        low = b["n"].lower()
        if H.RE_BREAST.search(low):
            fam[low] += 1
            models_with[low].add(n)
            cubes_with[low] += b["cc"]
print("=== 胸相关骨名（distinct %d, 总骨数 %d）" % (len(fam), sum(fam.values())))
for k, v in fam.most_common():
    print("  %-32s 出现 %-4d models=%-4d cubes=%d" % (k, v, len(models_with[k]), cubes_with[k]))

# ---------------------------------------------------------------- 2. 每模型胸装配
def breast_bones(n):
    out = []
    for b in F[n]["bones"]:
        low = b["n"].lower()
        if H.RE_BREAST.search(low) and b["cc"] > 0:
            out.append(b)
    return out


def cubes_of(n, bone_names):
    s = set(bone_names)
    return [c for c in F[n]["cubes"] if c["b"] in s]


rows = []
for n in names:
    bb = breast_bones(n)
    if not bb:
        continue
    skin = [b for b in bb if not H.is_cloth(b["n"])]
    cloth = [b for b in bb if H.is_cloth(b["n"])]
    def pack(lst):
        cs = cubes_of(n, [b["n"] for b in lst])
        if not cs:
            return None
        dims = [sorted(c["s"]) for c in cs]
        return {
            "bones": [b["n"] for b in lst],
            "n": len(cs),
            "rot_frac": round(sum(1 for c in cs if c["rot"]) / len(cs), 3),
            "thick_med": round(st.median([d[0] for d in dims]), 3),
            "mid_med": round(st.median([d[1] for d in dims]), 3),
            "long_med": round(st.median([d[2] for d in dims]), 3),
            "long_max": round(max(d[2] for d in dims), 2),
            "bb": [round(min(c["bb"][i] for c in cs), 2) if i < 3 else
                   round(max(c["bb"][i] for c in cs), 2) for i in range(6)],
            "centers": [c["c"] for c in cs],
            "sizes": [c["s"] for c in cs],
            "rots": [c["r"] for c in cs],
            "rotflags": [c["rot"] for c in cs],
        }
    rows.append({"model": n, "skin": pack(skin), "cloth": pack(cloth),
                 "n_bones": len(bb)})

print("\n=== 有胸骨且有块的模型：%d" % len(rows))
sk = [r for r in rows if r["skin"]]
cl = [r for r in rows if r["cloth"]]
print("  皮肤版 %d 模型 / 衣服版 %d 模型 / 两者都有 %d" %
      (len(sk), len(cl), sum(1 for r in rows if r["skin"] and r["cloth"])))

print("\n--- 每模型胸块总数（皮肤版）分位")
print(H.stat([r["skin"]["n"] for r in sk]))
print("--- 块数分布桶")
buckets = Counter()
for r in sk:
    k = r["skin"]["n"]
    b = ("1" if k == 1 else "2-3" if k <= 3 else "4-7" if k <= 7 else
         "8-15" if k <= 15 else "16-30" if k <= 30 else "31-60" if k <= 60 else ">60")
    buckets[b] += 1
for k in ["1", "2-3", "4-7", "8-15", "16-30", "31-60", ">60"]:
    print("   %-6s %d" % (k, buckets[k]))

print("\n--- 旋转占比（皮肤版）")
rf = [r["skin"]["rot_frac"] for r in sk]
print(H.stat(rf))
print("   0 旋转的模型数:", sum(1 for x in rf if x == 0), " / ", len(rf))
print("   >80% 旋转:", sum(1 for x in rf if x > 0.8))

print("\n--- 厚度（最短轴）中位 皮肤 vs 衣服")
print("skin", H.stat([r["skin"]["thick_med"] for r in sk]))
print("cloth", H.stat([r["cloth"]["thick_med"] for r in cl]))

# ---------------------------------------------------------------- 3. 半球拟合
print("\n=== 半球拟合（对每侧分别拟合；用块中心）")
def fit_side(pts):
    s = H.fit_sphere(pts)
    return s

fit_rows = []
for r in sk:
    sk_ = r["skin"]
    cs_x = [c[0] for c in sk_["centers"]]
    sides = []
    if min(cs_x) < -0.6 and max(cs_x) > 0.6:
        left = [c for c in sk_["centers"] if c[0] > 0]
        right = [c for c in sk_["centers"] if c[0] < 0]
        if left:
            sides.append(left)
        if right:
            sides.append(right)
    else:
        sides.append(sk_["centers"])
    for side in sides:
        if len(side) < 5:
            continue
        f = fit_side(side)
        if f:
            c, rad, rms = f
            fit_rows.append({"model": r["model"], "n": len(side), "r": rad,
                             "rms": rms, "rms_rel": rms / rad if rad else None})

if fit_rows:
    print("拟合侧数", len(fit_rows))
    print("半径 r:", H.stat([x["r"] for x in fit_rows]))
    print("RMS:", H.stat([x["rms"] for x in fit_rows]))
    print("RMS/r:", H.stat([x["rms_rel"] for x in fit_rows if x["rms_rel"]]))
    best = sorted(fit_rows, key=lambda x: -x["n"])[:12]
    for b in best:
        print("   %-34s n=%-3d r=%.2f rms=%.2f (%.0f%%)" %
              (b["model"], b["n"], b["r"], b["rms"], 100 * b["rms"] / b["r"]))

with open(r"F:\Deepseek_harness\blockbench\tools\curve\out_breast.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False)
print("\nwrote out_breast.json")
