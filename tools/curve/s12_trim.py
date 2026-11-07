#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""躯干宽度剖面 v2：按 1 单位带统计，去掉离群宽片（bow/collar）后取包络。
对比 elysia/jingliu/nvshi/zhe/jizi 等，确认可用性。"""
import json
import math
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
C = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_chain.json", encoding="utf-8"))
BAND = 1.0


def torso_band_profile(n, trim=2.0):
    d = C[n]
    torso = set(d["torso_bones"])
    cs = [c for c in F[n]["cubes"] if c["b"] in torso]
    if not cs:
        return None
    bands = defaultdict(list)
    for c in cs:
        b0 = int(math.floor(c["bb"][1] / BAND))
        b1 = max(b0 + 1, int(math.ceil(c["bb"][4] / BAND)))
        for k in range(b0, b1):
            bands[k].append(c)
    out = {}
    for k, lst in bands.items():
        ws = [c["bb"][3] - c["bb"][0] for c in lst]
        med = st.median(ws)
        mad = st.median([abs(w - med) for w in ws]) or 0.2
        keep = [c for c in lst if (c["bb"][3] - c["bb"][0]) <= med + trim * mad * 1.4826 + 0.5]
        if not keep:
            keep = lst
        x0 = min(c["bb"][0] for c in keep)
        x1 = max(c["bb"][3] for c in keep)
        out[k * BAND] = {"w": x1 - x0, "w_all": max(c["bb"][3] for c in lst) - min(c["bb"][0] for c in lst),
                         "n": len(lst), "kept": len(keep)}
    return out


for n in ["hi3_elysia__ae12017978c2", "hsr_jingliu__d803a5536723", "nvshi__ee8cadc8a57a",
          "zhe_1__b0cffdb26058", "jizi__2c90d16c1e70", "bronya_reason4.2__7e7ed02b87cc"]:
    d = C[n]
    p = torso_band_profile(n)
    if not p:
        print(n, "no profile")
        continue
    leg_y = d["leg_y"] or 0
    arm_y = d["arm_y"]
    fb = d["foot_bottom"]
    Ht = d["head"]["top"] - fb
    print("=" * 70)
    print(n, "torso %.1f..%.1f (legPivot %.1f armPivot %.1f)" % (min(p), max(p), leg_y, arm_y))
    for y in sorted(p):
        if y < leg_y - 3 or y > arm_y + 3:
            continue
        v = p[y]
        t = (y - leg_y) / max(1e-6, (arm_y - leg_y))
        print("  y=%5.1f t=%.2f w=%5.1f (all %5.1f) n=%-3d %-26s" %
              (y, t, v["w"], v["w_all"], v["n"], "#" * int(v["w"])))
