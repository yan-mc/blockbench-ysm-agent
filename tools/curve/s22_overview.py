#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇总：区域方块预算、样例外貌表、身体块数分布。输出 doc_facts.md"""
import json
import statistics as st
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
C = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_chain.json", encoding="utf-8"))


def region(name):
    low = name.lower()
    if any(r.search(low) for r in (H.RE_HAIR,)):
        return "hair"
    if H.RE_BREAST.search(low):
        return "breast"
    if H.is_cape(low):
        return "cape"
    if H.is_skirt(low):
        return "skirt"
    if H.RE_FOOT.search(low):
        return "foot"
    if H.RE_LEG_LOW.search(low) or H.RE_LEG_UP.search(low):
        return "leg"
    if H.RE_HAND.search(low):
        return "hand"
    if H.RE_ARM.search(low):
        return "arm"
    if H.RE_NECK.search(low):
        return "neck"
    if H.RE_HEAD.search(low):
        return "head"
    if H.RE_TORSO_LOOSE.search(low) or H.RE_PELVIS.search(low):
        return "torso"
    return "other"


print("=== 总方块分布")
tot = [F[n]["n_cubes"] for n in F]
print("  全部模型 总块数", H.stat(tot))
body = []
for n in F:
    c = sum(1 for x in F[n]["cubes"] if region(x["b"]) not in ("hair", "cape"))
    body.append(c)
print("  身体块数（去发/披风）", H.stat(body))

print("\n=== 区域块数（全语料合计 / 有该区域的模型的中位）")
agg = Counter()
per = defaultdict(list)
for n in F:
    cnt = Counter()
    for c in F[n]["cubes"]:
        cnt[region(c["b"])] += 1
    for k, v in cnt.items():
        agg[k] += v
        per[k].append(v)
for k in sorted(agg, key=lambda x: -agg[x]):
    print("  %-7s 总计 %6d  有该区模型 %3d  中位 %5.1f  p75 %5.1f" %
          (k, agg[k], len(per[k]), st.median(per[k]), H.q(per[k], 0.75)))

print("\n=== 样例（三件套用）")
samples = ["hi3_elysia__ae12017978c2", "hsr_jingliu__d803a5536723", "jizi__2c90d16c1e70",
           "zhe_1__b0cffdb26058", "nvshi__ee8cadc8a57a", "ruanmei__20d0917bb915",
           "bronya_reason4.2__7e7ed02b87cc", "yujin__fcfee7c1d023",
           "gs_qz_yg__78b9dcf3d436", "miku__29a4a02e7c2a", "ba_toki_v1.2__f91cbef6c7a3"]
for n in samples:
    if n not in F:
        continue
    cnt = Counter()
    for c in F[n]["cubes"]:
        cnt[region(c["b"])] += 1
    seg = len([s for s in C[n]["segs"] if s["n"] > 0]) if n in C else -1
    print("  %-34s 总%5d 身%5d 胸%4d 腿%4d 裙%4d 发%5d 躯干段%d" %
          (n[:34], F[n]["n_cubes"], sum(v for k, v in cnt.items() if k not in ("hair", "cape")),
           cnt["breast"], cnt["leg"] + cnt["foot"], cnt["skirt"], cnt["hair"], seg))
