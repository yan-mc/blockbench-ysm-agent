#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""胸前突起量（与骨名无关）：中线 |x|<3 的前表面 z 剖面，量 bulge 高度与峰值位置。"""
import json
import math
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
C = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_chain.json", encoding="utf-8"))


def front_profile(n, halfw=3.0, step=0.5):
    """返回 {y: z_front}（z 越小越前），只统计跨中线附近的躯干/胸骨方块。"""
    d = C[n]
    torso = set(d["torso_bones"])
    cs = []
    for c in F[n]["cubes"]:
        low = c["b"].lower()
        if any(r.search(low) for r in (H.RE_HAIR, H.RE_CAPE, H.RE_WEAPON)):
            continue
        if H.RE_ARM.search(low) or H.RE_HAND.search(low):
            continue
        if not (c["b"] in torso or H.RE_BREAST.search(low) or H.RE_PELVIS.search(low)
                or H.is_skirt(low) or H.RE_LEG_UP.search(low) or H.RE_LEG_LOW.search(low)):
            continue
        # 跨中线 ±halfw 内
        if c["bb"][0] > halfw or c["bb"][3] < -halfw:
            continue
        cs.append(c)
    bands = defaultdict(lambda: 1e9)
    for c in cs:
        b0 = int(math.floor(c["bb"][1] / step))
        b1 = max(b0 + 1, int(math.ceil(c["bb"][4] / step)))
        for k in range(b0, b1):
            bands[k] = min(bands[k], c["bb"][2])
    return {round(k * step, 2): v for k, v in bands.items()}


rows = []
for n in sorted(C):
    d = C[n]
    arm_y, leg_y = d["arm_y"], d["leg_y"]
    if not arm_y or not leg_y:
        continue
    pr = front_profile(n)
    ys = [y for y in sorted(pr) if leg_y - 2 <= y <= arm_y + 1]
    if len(ys) < 10:
        continue
    # 胸带 = 上 35% 躯干；腰 = 中间
    chest = [y for y in ys if y >= arm_y - 9]
    waistb = [y for y in ys if leg_y + 2 <= y <= (leg_y + arm_y) / 2]
    if not chest or not waistb:
        continue
    waist_z = st.median([pr[y] for y in waistb])
    zmin_chest = min(pr[y] for y in chest)
    y_peak = min(chest, key=lambda y: pr[y])
    bulge = waist_z - zmin_chest
    # 峰值位置（相对躯干）
    t = (y_peak - leg_y) / (arm_y - leg_y)
    # 只有明显前突（>1）才算有胸
    rows.append({"model": n, "bulge": round(bulge, 2), "t": round(t, 3),
                 "waist_z": round(waist_z, 2), "chest_z": round(zmin_chest, 2),
                 "torso": round(arm_y - leg_y, 1),
                 "cubes": F[n]["n_cubes"]})

print("可测", len(rows))
has = [r for r in rows if r["bulge"] > 1.0]
print("有明显胸前突（>1 单位）: %d = %.0f%%" % (len(has), 100 * len(has) / len(rows)))
print("前突量（全部）", H.stat([r["bulge"] for r in rows]))
print("前突量（明显者）", H.stat([r["bulge"] for r in has]))
print("峰值相对高度 t", H.stat([r["t"] for r in has]))
print("前突/躯干长", H.stat([r["bulge"] / r["torso"] for r in has]))
print("\n前突最大 12 个")
for r in sorted(rows, key=lambda r: -r["bulge"])[:12]:
    print("  %-34s bulge=%5.1f t=%.2f chest_z=%.1f waist_z=%.1f" %
          (r["model"][:34], r["bulge"], r["t"], r["chest_z"], r["waist_z"]))
print("\n前突 <1 的（平胸/忽略）:", sum(1 for r in rows if r["bulge"] <= 1.0))
with open(r"F:\Deepseek_harness\blockbench\tools\curve\out_bulge.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False)
