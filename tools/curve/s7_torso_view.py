#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""躯干剖面可视化：看清每个模型到底怎么收腰。"""
import math
import sys
from collections import defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()


def show(n, bones=None, step=0.5):
    CS = F[n]["cubes"]
    if bones:
        bs = {b.lower() for b in bones}
        CS = [c for c in CS if c["b"].lower() in bs]
    if not CS:
        print("  (no cubes)")
        return
    lo = min(c["bb"][1] for c in CS)
    hi = max(c["bb"][4] for c in CS)
    prof = defaultdict(lambda: [1e9, -1e9])
    bybone = defaultdict(lambda: defaultdict(lambda: [1e9, -1e9]))
    for c in CS:
        b0, b1 = int(math.floor(c["bb"][1] / step)), int(math.ceil(c["bb"][4] / step))
        for k in range(b0, b1):
            prof[k][0] = min(prof[k][0], c["bb"][0])
            prof[k][1] = max(prof[k][1], c["bb"][3])
            bb = bybone[c["b"]][k]
            bb[0] = min(bb[0], c["bb"][0])
            bb[1] = max(bb[1], c["bb"][3])
    ks = sorted(prof)
    print("  y     width  bar                    |  骨骼归属")
    for k in ks:
        w = prof[k][1] - prof[k][0]
        owners = [bn for bn in bybone if k in bybone[bn] and
                  abs((bybone[bn][k][1] - bybone[bn][k][0]) - w) < 0.01]
        print("  %6.2f %5.1f  %-24s | %s" % (k * step, w, "#" * int(w), ",".join(owners)[:40]))


for n in ["hi3_elysia__ae12017978c2", "hsr_jingliu__d803a5536723", "nvshi__ee8cadc8a57a",
          "zhe_1__b0cffdb26058", "otto_apocalypse__664c5076856a"]:
    print("=" * 70, n, "cubes", F[n]["n_cubes"])
    show(n, ["UpBody", "DownBody", "UpperBody", "Upper_body", "Chest", "Body"])
