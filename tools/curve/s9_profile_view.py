#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查剖面：ASCII 打印 + 地标标注。"""
import json
import sys

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

P = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_profile.json", encoding="utf-8"))


def show(n):
    d = P[n]
    hm, pv, fb = d["head"], d["pivots"], d["foot_bottom"]
    top = hm["top"]
    Ht = top - fb
    print("=" * 76)
    print(n, "cubes", d["cubes"], "head_h", round(hm["h"], 1), "H", round(Ht, 1),
          "头身比", round(Ht / hm["h"], 2))
    ys = sorted(float(k) for k in d["profile"])
    print(" y     t     w      d    |  bar(w)                     | 含x0骨架")
    for y in ys:
        v = d["profile"][str(y)] if str(y) in d["profile"] else d["profile"][repr(y)]
        t = (y - fb) / Ht
        mark = ""
        if abs(y - pv.get("leg_y", -999)) < 0.3:
            mark += " <legPivot"
        if abs(y - pv.get("arm_y", -999)) < 0.3:
            mark += " <armPivot"
        if abs(y - pv.get("knee_y", -999)) < 0.3:
            mark += " <knee"
        if abs(y - pv.get("ankle_y", -999)) < 0.3:
            mark += " <ankle"
        print(" %5.1f %.2f %5.1f %5.1f |%-26s| %s%s" %
              (y, t, v["w"], v["d"], "#" * int(v["w"]), ",".join(v["bones"])[:30], mark))


for n in ["hi3_elysia__ae12017978c2", "hsr_jingliu__d803a5536723"]:
    show(n)
