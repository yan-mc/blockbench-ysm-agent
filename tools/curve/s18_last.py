#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收尾统计：腿部宽度序列 / 腿根与胯的搭接 / 手 / 颈 / 头身比 / 肩宽。写 out_last.json"""
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()


def bmap(n):
    return {b["n"]: b for b in F[n]["bones"]}


def bone(n, ln):
    for b in F[n]["bones"]:
        if b["n"].lower() == ln:
            return b
    return None


def band_widths(cs, step=1.0):
    if not cs:
        return {}
    lo = min(c["bb"][1] for c in cs)
    hi = max(c["bb"][4] for c in cs)
    out = {}
    y = lo
    while y < hi:
        sel = [c for c in cs if c["bb"][1] < y + step and c["bb"][4] > y]
        if sel:
            out[round(y, 1)] = (max(c["bb"][3] for c in sel) - min(c["bb"][0] for c in sel),
                                max(c["bb"][5] for c in sel) - min(c["bb"][2] for c in sel))
        y += step
    return out


# ---------------------------------------------------------------- 腿部宽度序列
print("=== 腿：从胯到踝的宽度/厚度序列（左腿，块数>=12 的模型）")
leg_rows = []
for n in sorted(F):
    up, lo, ft = bone(n, "leftleg"), bone(n, "leftlowerleg"), bone(n, "leftfoot")
    if not up:
        continue
    cs = [c for c in F[n]["cubes"] if lo and c["b"] == lo["n"]]
    csu = [c for c in F[n]["cubes"] if c["b"] == up["n"]]
    allc = csu + cs
    if len(allc) < 12:
        continue
    top = max(c["bb"][4] for c in allc)
    bot = min(c["bb"][1] for c in allc)
    if top - bot < 6:
        continue
    bw = band_widths(allc)
    ys = sorted(bw)
    ws = [bw[y][0] for y in ys]
    ds = [bw[y][1] for y in ys]
    k = len(ys)
    def at(frac):
        i = min(k - 1, max(0, int(round(frac * (k - 1)))))
        return ws[i], ds[i]
    w_thigh, d_thigh = at(0.15)
    w_knee, d_knee = at(0.45)
    w_calf, d_calf = at(0.65)
    w_ankle, d_ankle = at(0.95)
    leg_rows.append({
        "model": n, "n": len(allc), "top": top, "bot": bot,
        "w_thigh": w_thigh, "w_knee": w_knee, "w_calf": w_calf, "w_ankle": w_ankle,
        "knee_thigh": w_knee / w_thigh if w_thigh else None,
        "calf_knee": w_calf / w_knee if w_knee else None,
        "ankle_calf": w_ankle / w_calf if w_calf else None,
        "levels": k,
    })
print(" 模型数", len(leg_rows))
for k in ("w_thigh", "w_knee", "w_calf", "w_ankle"):
    print("  %-8s %s" % (k, H.stat([r[k] for r in leg_rows])))
for k in ("knee_thigh", "calf_knee", "ankle_calf"):
    print("  %-11s %s" % (k, H.stat([r[k] for r in leg_rows if r[k]])))
print("  块数", H.stat([r["n"] for r in leg_rows]))
print("\n top 8 腿：")
for r in sorted(leg_rows, key=lambda r: -r["n"])[:8]:
    print("   %-34s n=%-3d thigh=%.1f knee=%.1f calf=%.1f ankle=%.1f | knee/thigh=%.2f calf/knee=%.2f" %
          (r["model"][:34], r["n"], r["w_thigh"], r["w_knee"], r["w_calf"], r["w_ankle"],
           r["knee_thigh"], r["calf_knee"]))

# ---------------------------------------------------------------- 腿根搭接
print("\n=== 腿根是否伸进胯里（防漏缝）")
ov = []
for n in sorted(F):
    up = bone(n, "leftleg")
    if not up or not up["bb"]:
        continue
    cs = [c for c in F[n]["cubes"] if c["b"] == up["n"]]
    if not cs:
        continue
    top = max(c["bb"][4] for c in cs)
    ov.append((n, top - up["pivot"][1]))
print("  腿骨最高点 - 腿枢轴:", H.stat([o for _, o in ov]))
print("  >0（伸进胯）占比: %.0f%%" % (100 * sum(1 for _, o in ov if o > 0) / len(ov)))
print("  >2 占比: %.0f%%" % (100 * sum(1 for _, o in ov if o > 2) / len(ov)))

# ---------------------------------------------------------------- 手
print("\n=== 手")
hand_c = []
hand_w = []
for n in sorted(F):
    hs = [b for b in F[n]["bones"] if b["n"].lower() in ("lefthand", "righthand")]
    if not hs:
        continue
    for h in hs:
        if h["cc"] and h["bb"]:
            hand_c.append(h["cc"])
            hand_w.append(max(h["bb"][3] - h["bb"][0], h["bb"][5] - h["bb"][2]))
print("  单只手段数", H.stat(hand_c))
print("  手的横向尺寸", H.stat(hand_w))
print("  有指骨模型数 9；有手套骨 4")

# ---------------------------------------------------------------- 颈
print("\n=== 颈")
rows = []
for n in sorted(F):
    nk = bone(n, "neck")
    al = bone(n, "allhead") or bone(n, "head")
    if not nk or not nk["cc"] or not nk["bb"]:
        continue
    rows.append({"model": n, "n": nk["cc"],
                 "w": nk["bb"][3] - nk["bb"][0],
                 "h": nk["bb"][4] - nk["bb"][1],
                 "head_w": (al["bb"][3] - al["bb"][0]) if al and al["bb"] else None})
print("  有独立 neck 骨且有块:", len(rows), "/", len(F))
if rows:
    print("  neck 块数", H.stat([r["n"] for r in rows]))
    print("  neck 宽", H.stat([r["w"] for r in rows]))
    print("  neck 宽/头宽", H.stat([r["w"] / r["head_w"] for r in rows if r["head_w"]]))

# ---------------------------------------------------------------- 头身比 / 肩宽
print("\n=== 头身比（头=AllHead+Head 直接块）")
props = []
for n in sorted(F):
    names = {b["n"] for b in F[n]["bones"] if b["n"].lower() in ("allhead", "head")}
    cs = [c for c in F[n]["cubes"] if c["b"] in names]
    if not cs:
        continue
    y0 = min(c["bb"][1] for c in cs)
    y1 = max(c["bb"][4] for c in cs)
    x0 = min(c["bb"][0] for c in cs)
    x1 = max(c["bb"][3] for c in cs)
    fb = min([b["bb"][1] for b in F[n]["bones"] if b["bb"] and H.RE_FOOT.search(b["n"].lower())]
             or [None])
    if fb is None:
        continue
    Ht = y1 - fb
    if Ht < 15:
        continue
    leg = bone(n, "leftleg")
    la = bone(n, "leftarm")
    props.append({
        "model": n, "H": round(Ht, 2), "head_h": round(y1 - y0, 2), "head_w": round(x1 - x0, 2),
        "ratio": round(Ht / (y1 - y0), 2) if y1 > y0 else None,
        "leg_share": round((leg["pivot"][1] - fb) / Ht, 3) if leg else None,
        "arm_x": abs(la["pivot"][0]) if la else None,
        "leg_x": abs(leg["pivot"][0]) if leg else None,
        "cubes": F[n]["n_cubes"],
    })
print("  模型数", len(props))
print("  头身比", H.stat([p["ratio"] for p in props if p["ratio"]]))
print("  head_h/H", H.stat([p["head_h"] / p["H"] for p in props]))
print("  腿长占比", H.stat([p["leg_share"] for p in props if p["leg_share"]]))
print("  臂枢轴 |x|", H.stat([p["arm_x"] for p in props if p["arm_x"]]))
print("  腿枢轴 |x|", H.stat([p["leg_x"] for p in props if p["leg_x"]]))
print("  肩枢轴间距/胯枢轴间距", H.stat([2 * p["arm_x"] / (2 * p["leg_x"]) for p in props
                                       if p["arm_x"] and p["leg_x"]]))
b = Counter()
for p in props:
    v = p["ratio"]
    if not v:
        continue
    k = ("<4.5" if v < 4.5 else "4.5-5" if v < 5 else "5-5.5" if v < 5.5 else
         "5.5-6" if v < 6 else "6-6.5" if v < 6.5 else "6.5-7" if v < 7 else "7-8" if v < 8 else ">=8")
    b[k] += 1
for k in ["<4.5", "4.5-5", "5-5.5", "5.5-6", "6-6.5", "6.5-7", "7-8", ">=8"]:
    print("     %-8s %d" % (k, b[k]))
print("  腿长占比桶:")
b = Counter()
for p in props:
    v = p["leg_share"]
    if v is None:
        continue
    k = ("<0.42" if v < 0.42 else "0.42-0.46" if v < 0.46 else "0.46-0.5" if v < 0.5
         else "0.5-0.54" if v < 0.54 else ">=0.54")
    b[k] += 1
for k in ["<0.42", "0.42-0.46", "0.46-0.5", "0.5-0.54", ">=0.54"]:
    print("     %-9s %d" % (k, b[k]))

with open(r"F:\Deepseek_harness\blockbench\tools\curve\out_last.json", "w", encoding="utf-8") as f:
    json.dump({"legs": leg_rows, "props": props}, f, ensure_ascii=False)
print("\nwrote out_last.json")
