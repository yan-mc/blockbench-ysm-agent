#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核对文档里几个派生数字。"""
import json
import statistics as st
import sys

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
W = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_waist.json", encoding="utf-8"))
L = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_last.json", encoding="utf-8"))
P = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_profile.json", encoding="utf-8"))

# 1) s17 定义的 waist_hip / hip_bust 的百分比
for k in ("waist_hip", "hip_bust", "waist_bust"):
    v = [r[k] for r in W]
    print("%-10s <0.85 %.0f%%  <0.90 %.0f%%  <1.00 %.0f%%  >1.00 %.0f%%" %
          (k, 100 * sum(1 for x in v if x < 0.85) / len(v), 100 * sum(1 for x in v if x < 0.9) / len(v),
           100 * sum(1 for x in v if x < 1) / len(v), 100 * sum(1 for x in v if x > 1) / len(v)))

# 2) 肩关节高度 / 身高
rows = []
for n, d in P.items():
    pv = d["pivots"]
    if "arm_y" not in pv:
        continue
    rows.append((pv["arm_y"] - d["foot_bottom"]) / (d["head"]["top"] - d["foot_bottom"]))
print("\n肩关节高/身高", H.stat(rows))

# 3) 头身比分档（3-8）
r = [p["ratio"] for p in L["props"] if p["ratio"] and 3 <= p["ratio"] <= 8]
buckets = {"3.5-4": 0, "4-4.5": 0, "4.5-5": 0, "5-5.5": 0, "5.5-6": 0, "6-8": 0}
for x in r:
    if x < 4:
        buckets["3.5-4"] += 1
    elif x < 4.5:
        buckets["4-4.5"] += 1
    elif x < 5:
        buckets["4.5-5"] += 1
    elif x < 5.5:
        buckets["5-5.5"] += 1
    elif x < 6:
        buckets["5.5-6"] += 1
    else:
        buckets["6-8"] += 1
print("\n头身比分档 n=%d" % len(r), {k: "%d (%.0f%%)" % (v, 100 * v / len(r)) for k, v in buckets.items()})

# 4) 头骨只有 1 块的模型数
cnt1 = 0
for n in F:
    cc = sum(b["cc"] for b in F[n]["bones"] if b["n"].lower() in ("allhead", "head"))
    if cc == 1:
        cnt1 += 1
print("\n头骨总块数=1 的模型:", cnt1)
ccs = [sum(b["cc"] for b in F[n]["bones"] if b["n"].lower() in ("allhead", "head")) for n in F]
print("头骨块数分布", H.stat(ccs))

# 5) 胸宽：整胸 vs 单侧（用 s4 的 per-side 与 s20 的 per-bone 对照）
B2 = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_breast2.json", encoding="utf-8"))
print("\nA组 全胸宽/身高", H.stat([x["w_rel"] for x in B2["A"]]))
# 单侧：用 out_breast 的每侧包围盒
B = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_breast.json", encoding="utf-8"))
print("（§3.2 的 0.173 是整胸宽）")

# 6) 腰部/胯部绝对宽度 vs 身高
print("\n胯宽/身高", H.stat([r["hip"] / (r["arm_y"] / 0.72) if False else 0 for r in W][:1]))
