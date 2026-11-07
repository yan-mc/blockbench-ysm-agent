#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核心轮廓（躯干链+骨盆+胸+腿+裙，排除手臂/手/头发/披风/武器）的宽比统计。
这是「身体轮廓」而不是「含手臂剪影」。输出 out_core.json
"""
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
C = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_chain.json", encoding="utf-8"))


def bmap(n):
    return {b["n"]: b for b in F[n]["bones"]}


def is_core_bone(name):
    low = name.lower()
    if any(r.search(low) for r in (H.RE_HAIR, H.RE_CAPE, H.RE_WEAPON)):
        return False
    if H.RE_ARM.search(low) or H.RE_HAND.search(low):
        return False
    return True


def profile(n, step=0.5):
    d = C[n]
    torso = set(d["torso_bones"])
    core = [c for c in F[n]["cubes"] if c["b"] in torso or
            (is_core_bone(c["b"]) and (H.RE_PELVIS.search(c["b"].lower()) or
                                       H.is_skirt(c["b"]) or
                                       H.RE_BREAST.search(c["b"].lower()) or
                                       H.RE_LEG_UP.search(c["b"].lower()) or
                                       H.RE_LEG_LOW.search(c["b"].lower()) or
                                       H.RE_FOOT.search(c["b"].lower())))]
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
    return out, core


rows = []
for n in sorted(C):
    pr, core = profile(n)
    if len(pr) < 10 or not core:
        continue
    d = C[n]
    ys = sorted(pr)
    arm_y, leg_y = d["arm_y"], d["leg_y"]
    if not arm_y or not leg_y:
        continue
    def band(a, b, mode="max"):
        v = [pr[y] for y in ys if a <= y <= b]
        if not v:
            return None
        return max(v) if mode == "max" else min(v)
    bust = band(arm_y - 8, arm_y - 1)
    waist = band(leg_y + 2, arm_y - 7, "min")
    hip = band(leg_y - 5, leg_y + 3)
    if not (bust and waist and hip):
        continue
    rows.append({
        "model": n, "bust": round(bust, 2), "waist": round(waist, 2), "hip": round(hip, 2),
        "waist_bust": round(waist / bust, 3), "waist_hip": round(waist / hip, 3),
        "hip_bust": round(hip / bust, 3), "n_core": len(core),
        "arm_y": arm_y, "leg_y": leg_y,
    })

print("可测模型", len(rows))
for k in ("waist_bust", "waist_hip", "hip_bust"):
    v = [r[k] for r in rows]
    print("%-11s %s" % (k, H.stat(v)))
    print("     <0.85: %.0f%%  <0.90: %.0f%%  <1: %.0f%%" %
          (100 * sum(1 for x in v if x < 0.85) / len(v),
           100 * sum(1 for x in v if x < 0.9) / len(v),
           100 * sum(1 for x in v if x < 1) / len(v)))

print("\n按块数分层的腰比（<300 块 vs >=300 块）")
for lo, hi, tag in [(0, 300, "低模 (<300 块)"), (300, 10 ** 9, "高模 (>=300 块)")]:
    sub = [r for r in rows if lo <= F[r["model"]]["n_cubes"] < hi]
    if sub:
        print("  %-16s n=%-3d waist_bust=%s waist_hip=%s" %
              (tag, len(sub), H.stat([x["waist_bust"] for x in sub]),
               H.stat([x["waist_hip"] for x in sub])))

print("\n最细腰 top12")
for r in sorted(rows, key=lambda r: r["waist_bust"])[:12]:
    print("  %-34s bust=%5.1f waist=%5.1f hip=%5.1f  w/bu=%.2f w/hip=%.2f" %
          (r["model"][:34], r["bust"], r["waist"], r["hip"], r["waist_bust"], r["waist_hip"]))
print("\n最不收腰 top8")
for r in sorted(rows, key=lambda r: -r["waist_bust"])[:8]:
    print("  %-34s bust=%5.1f waist=%5.1f hip=%5.1f  w/bu=%.2f w/hip=%.2f" %
          (r["model"][:34], r["bust"], r["waist"], r["hip"], r["waist_bust"], r["waist_hip"]))

with open(r"F:\Deepseek_harness\blockbench\tools\curve\out_core.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False)
print("\nwrote out_core.json")
