#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""胸的三维分布：方位角/仰角覆盖、层数、尺寸谱 —— 判断"半球/分层/斜切"。"""
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
B = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_breast.json", encoding="utf-8"))
by = {r["model"]: r for r in B}

models = ["hi3_elysia__ae12017978c2", "jizi__2c90d16c1e70", "ruanmei__20d0917bb915",
          "hsr_jingliu__d803a5536723", "zhe_1__b0cffdb26058", "yujin__fcfee7c1d023",
          "bronya_reason4.2__7e7ed02b87cc", "nvshi__ee8cadc8a57a"]

print("%-34s %-3s %4s %5s %5s %5s | %-28s | %s" %
      ("model", "sd", "n", "sz_md", "rot_md", "r", "方位角扇区(前=0°,右+90°)" , "仰角分位"))
for n in models:
    r = by.get(n)
    if not r or not r["skin"]:
        continue
    s = r["skin"]
    cs = list(zip(s["centers"], s["sizes"], s["rots"], s["rotflags"]))
    for side in ("L", "R"):
        items = [c for c in cs if (c[0][0] > 0) == (side == "L")]
        if len(items) < 5:
            continue
        cx = st.mean([i[0][0] for i in items])
        cy = st.mean([i[0][1] for i in items])
        cz = st.mean([i[0][2] for i in items])
        # 胸的"外法向"近似：指向 -z（前）
        az = []
        el = []
        for (c, sz, ro, rf) in items:
            dx, dy, dz = c[0] - cx, c[1] - cy, c[2] - cz
            a = math.degrees(math.atan2(dx, -dz))  # 0=正前，+右
            az.append(a)
            hor = math.hypot(dx, dz)
            el.append(math.degrees(math.atan2(dy, hor)))
        # 扇区计数（每 45°）
        sec = Counter(int((a + 180) // 45) for a in az)
        secstr = " ".join("%d" % sec.get(i, 0) for i in range(8))
        fit = H.fit_sphere([i[0] for i in items]) if len(items) >= 6 else None
        szm = st.median([sorted(i[1])[0] for i in items])
        rotm = st.median([math.degrees(math.acos(max(-1, min(1, (lambda R: (R[0][0] + R[1][1] + R[2][2] - 1) / 2)([[1,0,0],[0,1,0],[0,0,1]]))))) for i in items]) if False else None
        print("%-34s %-3s %4d %5.1f %5s %5s | %-28s | %.0f..%.0f" %
              (n[:34], side, len(items), szm, "-", ("%.2f" % fit[1]) if fit else "-",
               secstr, H.q(el, 0.1), H.q(el, 0.9)))

print("\n=== 每 1 单位 y 层的块数（看分层）")
for n in models:
    r = by.get(n)
    if not r or not r["skin"]:
        continue
    s = r["skin"]
    for side in ("L",):
        items = [c for c, sz, ro, rf in zip(s["centers"], s["sizes"], s["rots"], s["rotflags"])
                 if (c[0] > 0) == (side == "L")]
        if len(items) < 10:
            continue
        ys = [c[1] for c in items]
        lo, hi = min(ys), max(ys)
        bands = defaultdict(int)
        for y in ys:
            bands[int((y - lo) // 1.0)] += 1
        print("  %-34s y层 %d 层: %s" % (n[:34], int(hi - lo) + 1,
                                         " ".join("%d" % bands.get(i, 0) for i in range(int(hi - lo) + 1))))

print("\n=== 尺寸谱（每侧，所有大胸模型）")
allsz = []
for r in B:
    s = r["skin"]
    if not s or s["n"] < 8:
        continue
    for sz in s["sizes"]:
        allsz.append(sorted(sz))
if allsz:
    for i in range(3):
        print("  第%d薄边" % (i + 1), H.stat([x[i] for x in allsz]))
