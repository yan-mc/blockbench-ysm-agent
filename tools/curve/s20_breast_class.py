#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""胸骨分类：局部胸凸 vs 整片上衣；各组块数/厚度/旋转/半径/位置。"""
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
B = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_breast.json", encoding="utf-8"))


def rot_angle(r):
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
    return math.degrees(math.acos(max(-1, min(1, (R[0][0] + R[1][1] + R[2][2] - 1) / 2))))


def landmarks(n):
    bones = F[n]["bones"]
    d = {}
    for b in bones:
        low = b["n"].lower()
        if low == "leftarm":
            d["arm"] = b["pivot"][1]
        if low == "leftleg":
            d["leg"] = b["pivot"][1]
    d["foot"] = min([b["bb"][1] for b in bones if b["bb"] and H.RE_FOOT.search(b["n"].lower())] or [0])
    hb = [b["bb"] for b in bones if b["n"].lower() in ("allhead", "head") and b["bb"]]
    if hb:
        d["head_top"] = max(b[4] for b in hb)
        d["head_h"] = max(b[4] - b[1] for b in hb)
    return d


rows = []
for r in B:
    s = r["skin"]
    if not s or s["n"] < 1:
        continue
    lm = landmarks(r["model"])
    if "head_top" not in lm or "arm" not in lm:
        continue
    Ht = lm["head_top"] - lm["foot"]
    bh = s["bb"][4] - s["bb"][1]
    cy = (s["bb"][1] + s["bb"][4]) / 2
    t = (cy - lm["leg"]) / (lm["arm"] - lm["leg"]) if lm["arm"] != lm["leg"] else None
    rows.append({
        "model": r["model"], "n": s["n"], "bones": s["bones"],
        "h": bh, "h_rel": round(bh / Ht, 3) if Ht else None,
        "w": s["bb"][3] - s["bb"][0], "d": s["bb"][5] - s["bb"][2],
        "thick": s["thick_med"], "mid": s["mid_med"], "long": s["long_med"],
        "rot": s["rot_frac"], "H": round(Ht, 1), "t": round(t, 2) if t else None,
        "w_rel": round((s["bb"][3] - s["bb"][0]) / Ht, 3) if Ht else None,
        "d_rel": round((s["bb"][5] - s["bb"][2]) / Ht, 3) if Ht else None,
        "cloth": bool(r["cloth"]),
    })

A = [x for x in rows if x["h_rel"] is not None and x["h_rel"] < 0.28]
Bg = [x for x in rows if x["h_rel"] is not None and x["h_rel"] >= 0.28]
print("总", len(rows), " 局部胸凸(A, h/H<0.28):", len(A), " 整片上衣(B):", len(Bg))
print("\n--- A 组（局部胸凸）")
print("  块数/模型", H.stat([x["n"] for x in A]))
print("  块数/模型（>=20 块）", H.stat([x["n"] for x in A if x["n"] >= 20]))
print("  高度占比 h/H", H.stat([x["h_rel"] for x in A]))
print("  宽度占比 w/H", H.stat([x["w_rel"] for x in A]))
print("  进深占比 d/H", H.stat([x["d_rel"] for x in A]))
print("  厚度(最薄轴)", H.stat([x["thick"] for x in A]))
print("  长度(最长轴)", H.stat([x["long"] for x in A]))
print("  旋转占比", H.stat([x["rot"] for x in A]))
print("  位置 t（0=腿枢轴,1=臂枢轴）", H.stat([x["t"] for x in A if x["t"] is not None]))
print("\n--- B 组（整片上衣）")
print("  块数/模型", H.stat([x["n"] for x in Bg]))
print("  高度占比", H.stat([x["h_rel"] for x in Bg]))
print("  厚度", H.stat([x["thick"] for x in Bg]))
print("  旋转占比", H.stat([x["rot"] for x in Bg]))

print("\n--- A 组按块数分档")
for lo, hi, tag in [(1, 3, "1-3 块"), (4, 9, "4-9"), (10, 19, "10-19"), (20, 39, "20-39"), (40, 999, "40+")]:
    sub = [x for x in A if lo <= x["n"] <= hi]
    if sub:
        print("  %-8s n=%-3d 厚度=%.2f 长度=%.2f 高度=%.1f 宽度=%.1f 进深=%.1f rot=%.2f" %
              (tag, len(sub), st.median([x["thick"] for x in sub]),
               st.median([x["long"] for x in sub]), st.median([x["h"] for x in sub]),
               st.median([x["w"] for x in sub]), st.median([x["d"] for x in sub]),
               st.median([x["rot"] for x in sub])))

print("\n--- A 组 20+ 块的全部模型")
for x in sorted([x for x in A if x["n"] >= 20], key=lambda x: -x["n"]):
    print("  %-34s n=%-3d h=%.1f w=%.1f d=%.1f thick=%.2f rot=%.2f t=%.2f bones=%s" %
          (x["model"][:34], x["n"], x["h"], x["w"], x["d"], x["thick"], x["rot"],
           x["t"] or -1, ",".join(x["bones"])[:28]))

print("\n--- 衣服版（bones 名含 cloth/armor/...）在 A 组里的厚度")
cl = [x for x in A if x["cloth"]]
print("  数量", len(cl), " 厚度", H.stat([x["thick"] for x in cl]))
print("  其中 <0.4 的:", sum(1 for x in cl if x["thick"] < 0.4))

with open(r"F:\Deepseek_harness\blockbench\tools\curve\out_breast2.json", "w", encoding="utf-8") as f:
    json.dump({"A": A, "B": Bg}, f, ensure_ascii=False)
