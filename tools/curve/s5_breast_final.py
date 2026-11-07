#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q1 收尾：旋转量、突出量、竖直剖面、皮肤/衣服双层关系、单骨 vs 双骨。"""
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
rows = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_breast.json", encoding="utf-8"))


def rot_angle(r):
    """绕轴组合后的总旋转角（deg）。"""
    ax, ay, az = [math.radians(x) for x in r]
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    Rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    Ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    Rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    def mm(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    R = mm(Rz, mm(Ry, Rx))
    tr = R[0][0] + R[1][1] + R[2][2]
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1) / 2))))


print("=== 旋转量（皮肤版，每块的总旋转角）")
allang = []
per_model = []
for r in rows:
    s = r["skin"]
    if not s:
        continue
    angs = [rot_angle(ro) for ro, rf in zip(s["rots"], s["rotflags"]) if rf]
    if angs:
        allang += angs
        per_model.append((r["model"], len(angs), st.median(angs), H.q(angs, 0.9)))
print("总块数", len(allang))
print("单块旋转角分位:", H.stat(allang))
buckets = Counter()
for a in allang:
    b = ("<=10" if a <= 10 else "10-20" if a <= 20 else "20-35" if a <= 35 else
         "35-50" if a <= 50 else "50-70" if a <= 70 else "70-90" if a <= 90 else ">90")
    buckets[b] += 1
tot = len(allang)
for k in ["<=10", "10-20", "20-35", "35-50", "50-70", "70-90", ">90"]:
    print("   %-6s %5d  %4.1f%%" % (k, buckets[k], 100 * buckets[k] / tot))

print("\n=== 每模型旋转角中位（>=10 块的模型）")
for m, n, med, p90 in sorted([p for p in per_model if p[1] >= 10], key=lambda x: -x[2])[:20]:
    print("   %-36s n=%-3d median=%.0f° p90=%.0f°" % (m[:36], n, med, p90))

print("\n=== 单骨 vs 双骨")
single = [r for r in rows if r["skin"] and len(r["skin"]["bones"]) == 1]
pair = [r for r in rows if r["skin"] and len(r["skin"]["bones"]) >= 2]
print("单骨（一个 Breast 含两侧）:", len(single), " 双骨:", len(pair))
print("  单骨块数", H.stat([r["skin"]["n"] for r in single]))
print("  双骨块数（两侧合计）", H.stat([r["skin"]["n"] for r in pair]))

print("\n=== 突出量：胸最前 z 相对躯干最前 z（负 z 为前）")
prot = []
for r in rows:
    s = r["skin"]
    if not s:
        continue
    n = r["model"]
    tz = None
    for b in F[n]["bones"]:
        low = b["n"].lower()
        if b["bb"] and low in ("upbody", "upperbody", "upper_body", "body", "chest"):
            tz = b["bb"][2] if tz is None else min(tz, b["bb"][2])
    if tz is None:
        continue
    bz = s["bb"][2]
    prot.append((n, tz - bz))
print("突出量（单位）", H.stat([p[1] for p in prot]))
print("  >1.0 的模型数", sum(1 for p in prot if p[1] > 1.0), "/", len(prot))
for n, d in sorted(prot, key=lambda x: -x[1])[:12]:
    print("   %-36s 突出 %.2f" % (n[:36], d))

print("\n=== 竖直剖面（大胸模型，按胸高归一化后的最大前突位置）")


def band_profile(centers, sizes, nband=8):
    ys = [c[1] for c in centers]
    lo, hi = min(ys), max(ys)
    if hi - lo < 1e-6:
        return None
    out = []
    for i in range(nband):
        a = lo + (hi - lo) * i / nband
        b = lo + (hi - lo) * (i + 1) / nband
        zs = [c[2] for c in centers if a <= c[1] <= b]
        out.append(min(zs) if zs else None)
    return out, lo, hi


big = [r for r in rows if r["skin"] and r["skin"]["n"] >= 25]
print("模型数", len(big))
agg = defaultdict(list)
for r in big:
    s = r["skin"]
    sides = defaultdict(list)
    for c, sz in zip(s["centers"], s["sizes"]):
        sides["L" if c[0] > 0 else "R"].append((c, sz))
    for side, items in sides.items():
        cs = [i[0] for i in items]
        ss = [i[1] for i in items]
        p = band_profile(cs, ss)
        if not p:
            continue
        prof, lo, hi = p
        if prof[0] is None:
            continue
        base = max(z for z in prof if z is not None)
        for i, z in enumerate(prof):
            if z is not None:
                agg[i].append(round(1 - (z - base), 1))  # 相对最大突出
for i in range(8):
    v = agg[i]
    if v:
        print("  band %d (y %d%%-%d%%): 相对前突 中位 %.1f (n=%d)" %
              (i, i * 12, (i + 1) * 12, st.median(v), len(v)))

print("\n=== 双层（皮肤+衣服）对比")
both = [r for r in rows if r["skin"] and r["cloth"]]
print("模型数", len(both))
ratios = []
for r in both:
    s, c = r["skin"], r["cloth"]
    ratios.append((r["model"], s["n"], c["n"], s["thick_med"], c["thick_med"],
                   c["bb"][2] - s["bb"][2], c["bb"][3] - s["bb"][3]))
print("%-36s %5s %5s %6s %6s %7s %7s" % ("model", "skinN", "clothN", "skinT", "clothT", "dzmin", "dxmax"))
for x in sorted(ratios, key=lambda x: -x[1])[:16]:
    print("%-36s %5d %5d %6.2f %6.2f %7.2f %7.2f" % x)

print("\n=== 全部模型里“胸骨挂在哪”")
par = Counter()
for n in F:
    for b in F[n]["bones"]:
        if H.RE_BREAST.search(b["n"].lower()) and b["cc"] > 0:
            par[(b["p"] or "-")] += 1
for k, v in par.most_common(12):
    print("   parent=%-24s %d" % (k, v))
