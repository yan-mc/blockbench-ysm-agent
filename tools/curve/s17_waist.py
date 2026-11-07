#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q2 定稿：真收腰（局部极小）判定 + 收腰深度 + 机制统计（分段/旋转/板厚）。"""
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H
import importlib
s16 = importlib.import_module("s16_core") if False else None

F = H.load()
C = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_chain.json", encoding="utf-8"))
CORE = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_core.json", encoding="utf-8"))
core_by = {r["model"]: r for r in CORE}


def bmap(n):
    return {b["n"]: b for b in F[n]["bones"]}


def core_profile(n, step=0.5):
    """与 s16 相同：躯干链 + 骨盆 + 胸 + 腿 + 裙，排除臂/手/发/披风。"""
    d = C[n]
    torso = set(d["torso_bones"])
    core = [c for c in F[n]["cubes"] if c["b"] in torso or
            (not any(r.search(c["b"].lower()) for r in (H.RE_HAIR, H.RE_CAPE, H.RE_WEAPON))
             and not H.RE_ARM.search(c["b"].lower()) and not H.RE_HAND.search(c["b"].lower())
             and (H.RE_PELVIS.search(c["b"].lower()) or H.is_skirt(c["b"])
                  or H.RE_BREAST.search(c["b"].lower()) or H.RE_LEG_UP.search(c["b"].lower())
                  or H.RE_LEG_LOW.search(c["b"].lower()) or H.RE_FOOT.search(c["b"].lower())))]
    slices = defaultdict(list)
    for c in core:
        b0 = int(math.floor(c["bb"][1] / step))
        b1 = max(b0 + 1, int(math.ceil(c["bb"][4] / step)))
        for k in range(b0, b1):
            slices[k].append(c)
    out = {}
    for k, lst in slices.items():
        ivs = sorted((c["bb"][0], c["bb"][3]) for c in lst)
        runs = []
        for x0, x1 in ivs:
            if runs and x0 <= runs[-1][1] + 1e-6:
                runs[-1][1] = max(runs[-1][1], x1)
            else:
                runs.append([x0, x1])
        cand = [r for r in runs if r[0] <= 0 <= r[1]]
        if not cand:
            continue
        best = max(cand, key=lambda r: r[1] - r[0])
        out[round(k * step, 2)] = best[1] - best[0]
    return out


rows = []
for n in sorted(C):
    d = C[n]
    arm_y, leg_y = d["arm_y"], d["leg_y"]
    if not arm_y or not leg_y:
        continue
    pr = core_profile(n)
    ys = [y for y in sorted(pr) if leg_y <= y <= arm_y - 1]
    if len(ys) < 10:
        continue
    # 局部极小：在腿枢轴 +2 到 臂枢轴 -4 之间找最小
    cand = [y for y in ys if leg_y + 2 <= y <= arm_y - 4]
    if len(cand) < 6:
        continue
    y_w = min(cand, key=lambda y: pr[y])
    w_w = pr[y_w]
    below = [pr[y] for y in ys if leg_y <= y <= y_w - 1.5]
    above = [pr[y] for y in ys if y_w + 1.5 <= y <= arm_y - 1]
    if not below or not above:
        continue
    hip = max(below)
    bust = max(above)
    pinch = (hip > 1.1 * w_w) and (bust > 1.1 * w_w)
    rows.append({
        "model": n, "y_waist": y_w, "waist": round(w_w, 2),
        "hip": round(hip, 2), "bust": round(bust, 2),
        "torso_len": round(arm_y - leg_y, 1),
        "t_waist": round((y_w - leg_y) / (arm_y - leg_y), 3),
        "pinch": pinch,
        "depth": round(min(hip, bust) / w_w, 3) if w_w else None,
        "waist_hip": round(w_w / hip, 3), "waist_bust": round(w_w / bust, 3),
        "hip_bust": round(hip / bust, 3),
    })

print("可测", len(rows))
pin = [r for r in rows if r["pinch"]]
print("真收腰（腰比上下都窄 10%%以上）: %d = %.0f%%" % (len(pin), 100 * len(pin) / len(rows)))
print("收腰深度（窄侧/腰）", H.stat([r["depth"] for r in pin]))
print("腰位置（相对躯干 0=腿枢轴 1=臂枢轴）", H.stat([r["t_waist"] for r in pin]))
print("全样本 waist_hip", H.stat([r["waist_hip"] for r in rows]))
print("全样本 waist_bust", H.stat([r["waist_bust"] for r in rows]))
print("全样本 hip_bust", H.stat([r["hip_bust"] for r in rows]))
print("收腰模型 waist_hip", H.stat([r["waist_hip"] for r in pin]))
print("收腰模型 waist_bust", H.stat([r["waist_bust"] for r in pin]))

print("\n收腰最深的 12 个")
for r in sorted(pin, key=lambda r: -r["depth"])[:12]:
    print("  %-34s waist=%.1f@t=%.2f hip=%.1f bust=%.1f depth=%.2f w/hip=%.2f w/bu=%.2f" %
          (r["model"][:34], r["waist"], r["t_waist"], r["hip"], r["bust"], r["depth"],
           r["waist_hip"], r["waist_bust"]))
print("\n不收腰的例子")
for r in sorted([r for r in rows if not r["pinch"]], key=lambda r: r["waist_hip"])[:8]:
    print("  %-34s waist=%.1f hip=%.1f bust=%.1f w/hip=%.2f w/bu=%.2f" %
          (r["model"][:34], r["waist"], r["hip"], r["bust"], r["waist_hip"], r["waist_bust"]))

# ---- 机制
print("\n=== 收腰机制")
nseg = Counter()
for n in C:
    nseg[len([s for s in C[n]["segs"] if s["n"] > 0])] += 1
print("  躯干链带块骨数分布", dict(sorted(nseg.items())))
print("  躯干链骨数", H.stat([C[n]["n_torso_bones"] for n in C]))
print("  躯干链方块数", H.stat([C[n]["n_torso_cubes"] for n in C]))
print("  躯干方块旋转占比", H.stat([C[n]["rot_frac"] for n in C]))
print("  旋转占比 >=0.9 的模型:", sum(1 for n in C if C[n]["rot_frac"] >= 0.9), "/", len(C))

# 板厚与倾斜角
thick = []
zangs = []
yangs = []
for n in C:
    torso = set(C[n]["torso_bones"])
    for c in F[n]["cubes"]:
        if c["b"] not in torso:
            continue
        s = sorted(c["s"])
        thick.append(s[0])
        if c["rot"]:
            rx, ry, rz = c["r"]
            zangs.append(abs(rz))
            yangs.append(abs(ry))
print("  躯干方块最薄边", H.stat(thick))
print("  |rotZ|（侧板外倾）", H.stat(zangs))
print("  |rotY|（侧板绕竖轴）", H.stat(yangs))

with open(r"F:\Deepseek_harness\blockbench\tools\curve\out_waist.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False)
print("wrote out_waist.json")
