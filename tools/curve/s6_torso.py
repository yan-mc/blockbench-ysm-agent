#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q2 腰/胯：躯干切面宽度剖面、收腰机制（多段递减 vs 斜置方块）、宽比统计。"""
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
names = sorted(F.keys())

import re
SKIN_TORSO = re.compile(
    r"^(upbody|upperbody|upper_body|body|downbody|allbody|torso|waist|spine|chest)$")


def head_top(n):
    ys = []
    for b in F[n]["bones"]:
        low = b["n"].lower()
        if b["bb"] and ("allhead" in low or low == "head"):
            ys.append(b["bb"][4])
    return max(ys) if ys else None


def foot_bottom(n):
    ys = []
    for b in F[n]["bones"]:
        low = b["n"].lower()
        if b["bb"] and H.RE_FOOT.search(low) and "shoe" not in low:
            ys.append(b["bb"][1])
    return min(ys) if ys else None


def torso_cubes(n, regex=SKIN_TORSO):
    out = []
    for c in F[n]["cubes"]:
        if regex.match(c["b"].lower()):
            out.append(c)
    return out


rows = []
for n in names:
    cs = torso_cubes(n)
    if len(cs) < 4:
        continue
    top, bot = head_top(n), foot_bottom(n)
    if not top or not bot:
        continue
    hgt = top - bot
    if hgt < 20:
        continue
    # 0.25 单位切面
    prof = defaultdict(lambda: [1e9, -1e9, 1e9, -1e9])
    for c in cs:
        y0, y1 = c["bb"][1], c["bb"][4]
        b0, b1 = int(math.floor(y0 * 4)), int(math.ceil(y1 * 4))
        for k in range(b0, b1):
            p = prof[k]
            p[0] = min(p[0], c["bb"][0])
            p[1] = max(p[1], c["bb"][3])
            p[2] = min(p[2], c["bb"][2])
            p[3] = max(p[3], c["bb"][5])
    ys = sorted(prof)
    if len(ys) < 8:
        continue
    # 只取躯干连续段：从最低到最高
    w = {k: prof[k][1] - prof[k][0] for k in ys}
    d = {k: prof[k][3] - prof[k][2] for k in ys}
    ylo, yhi = ys[0], ys[-1]
    if yhi - ylo < 8:
        continue
    span = yhi - ylo
    # 归一化高度 t（0=躯干最低，1=最高）
    def at(t):
        k = int(round(ylo + span * t))
        k = min(ys, key=lambda x: abs(x - k))
        return w.get(k), d.get(k)
    # 腰部：中间 35%-65%
    mids = [w[k] for k in ys if 0.35 <= (k - ylo) / span <= 0.65]
    waist = min(mids) if mids else None
    upper = [w[k] for k in ys if (k - ylo) / span >= 0.8]
    lower = [w[k] for k in ys if (k - ylo) / span <= 0.2]
    bust = max(upper) if upper else None
    hip = max(lower) if lower else None
    wtop, dtop = at(0.9)
    wmid, dmid = at(0.5)
    wbot, dbot = at(0.1)
    rows.append({
        "model": n, "n_torso_cubes": len(cs), "h": hgt,
        "torso_span": span, "wtop": wtop, "wmid": wmid, "wbot": wbot,
        "dtop": dtop, "dmid": dmid, "dbot": dbot,
        "waist": waist, "bust": bust, "hip": hip,
        "w_waist_bust": waist / bust if waist and bust else None,
        "w_waist_hip": waist / hip if waist and hip else None,
        "w_hip_bust": hip / bust if hip and bust else None,
        "rot_frac": sum(1 for c in cs if c["rot"]) / len(cs),
        "n_torso_bones": len({c["b"] for c in cs}),
        "torso_bone_names": sorted({c["b"] for c in cs}),
    })

print("=== 可测躯干模型数", len(rows))
print("躯干块数", H.stat([r["n_torso_cubes"] for r in rows]))
print("躯干骨数", H.stat([r["n_torso_bones"] for r in rows]))
print("躯干竖直跨度", H.stat([r["torso_span"] for r in rows]))
print("\n宽度剖面（单位）")
for k in ("wtop", "wmid", "wbot"):
    print("  %-6s %s" % (k, H.stat([r[k] for r in rows])))
print("深度剖面（单位）")
for k in ("dtop", "dmid", "dbot"):
    print("  %-6s %s" % (k, H.stat([r[k] for r in rows])))
print("\n宽比")
for k in ("w_waist_bust", "w_waist_hip", "w_hip_bust"):
    v = [r[k] for r in rows if r[k]]
    print("  %-12s %s" % (k, H.stat(v)))
    print("      <1 的比例 %.0f%%  <0.9 的比例 %.0f%%" %
          (100 * sum(1 for x in v if x < 1) / len(v), 100 * sum(1 for x in v if x < 0.9) / len(v)))

print("\n=== 收腰机制：躯干方块旋转占比")
print("  全样本", H.stat([r["rot_frac"] for r in rows]))
print("  旋转占比=0 的模型", sum(1 for r in rows if r["rot_frac"] == 0), "/", len(rows))
print("  >0.5 的模型", sum(1 for r in rows if r["rot_frac"] > 0.5))

print("\n=== 躯干骨命名（出现率）")
cnt = Counter()
for r in rows:
    for b in r["torso_bone_names"]:
        cnt[b.lower()] += 1
for k, v in cnt.most_common(20):
    print("   %-24s %d (%.0f%%)" % (k, v, 100 * v / len(rows)))

print("\n=== 收腰幅度前列（waist/bust 最小）")
for r in sorted([r for r in rows if r["w_waist_bust"]], key=lambda r: r["w_waist_bust"])[:12]:
    print("  %-34s waist=%.1f bust=%.1f ratio=%.2f hip=%.1f w_waist_hip=%.2f bones=%s" %
          (r["model"][:34], r["waist"], r["bust"], r["w_waist_bust"], r["hip"] or -1,
           r["w_waist_hip"] or -1, ",".join(r["torso_bone_names"])[:46]))

print("\n=== 不收腰（ratio>=1）的模型数", sum(1 for r in rows if r["w_waist_bust"] and r["w_waist_bust"] >= 1))
for r in sorted([r for r in rows if r["w_waist_bust"] and r["w_waist_bust"] >= 1],
                key=lambda r: -r["w_waist_bust"])[:8]:
    print("  %-34s ratio=%.2f bones=%s" % (r["model"][:34], r["w_waist_bust"],
                                           ",".join(r["torso_bone_names"])[:50]))

with open(r"F:\Deepseek_harness\blockbench\tools\curve\out_torso.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False)
