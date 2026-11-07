#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q1 深化：胸的构造形状（分层/法向/角覆盖）、尺寸归一化、衣服版。"""
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
rows = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_breast.json", encoding="utf-8"))
by_model = {r["model"]: r for r in rows}


def head_w(n):
    """头宽（用 AllHead/Head 的方块 x 跨度），作为尺度基准。"""
    widths = []
    for b in F[n]["bones"]:
        low = b["n"].lower()
        if b["bb"] and ("allhead" in low or low == "head"):
            widths.append(b["bb"][3] - b["bb"][0])
    return max(widths) if widths else None


def torso_z_front(n):
    zs = []
    for b in F[n]["bones"]:
        low = b["n"].lower()
        if b["bb"] and H.RE_TORSO_LOOSE.search(low):
            zs.append(b["bb"][2])
    return min(zs) if zs else None


print("=== 每侧尺寸归一化（皮肤版，按 x 分侧）")
recs = []
for n, r in by_model.items():
    s = r["skin"]
    if not s:
        continue
    cs = list(zip(s["centers"], s["sizes"], s["rots"], s["rotflags"]))
    hw = head_w(n)
    sides = defaultdict(list)
    for c, sz, ro, rf in cs:
        sides["L" if c[0] > 0 else "R"].append((c, sz, ro, rf))
    for side, items in sides.items():
        xs = [i[0][0] for i in items]
        ys = [i[0][1] for i in items]
        zs = [i[0][2] for i in items]
        hx = [i[1][0] for i in items]
        hy = [i[1][1] for i in items]
        hz = [i[1][2] for i in items]
        recs.append({
            "model": n, "side": side, "n": len(items),
            "w": max(xs) - min(xs) + st.median(hx),
            "h": max(ys) - min(ys) + st.median(hy),
            "d": max(zs) - min(zs) + st.median(hz),
            "head_w": hw,
            "protr": None,
            "rot_frac": sum(1 for i in items if i[3]) / len(items),
        })
for k in ("n", "w", "h", "d"):
    print(" ", k, H.stat([r[k] for r in recs]))
print("  w/head_w", H.stat([r["w"] / r["head_w"] for r in recs if r["head_w"]]))
print("  d/head_w", H.stat([r["d"] / r["head_w"] for r in recs if r["head_w"]]))
print("  h/head_w", H.stat([r["h"] / r["head_w"] for r in recs if r["head_w"]]))

# ---------------------------------------------------------------- 形状：分层与法向
print("\n=== 高块数模型（每侧 >=20 块）的形状解剖")
big = sorted([r for r in recs if r["n"] >= 20], key=lambda r: -r["n"])
print("模型数", len(big))
hdr = "%-34s %-3s %4s %5s %5s %5s %6s %6s %5s" % ("model", "sd", "n", "w", "h", "d", "rfit", "rms/r", "bands")
print(hdr)
for r in big[:24]:
    n, side = r["model"], r["side"]
    s = by_model[n]["skin"]
    items = [(c, sz, ro) for c, sz, ro, rf in zip(s["centers"], s["sizes"], s["rots"], s["rotflags"])
             if (c[0] > 0) == (side == "L")]
    pts = [i[0] for i in items]
    fit = H.fit_sphere(pts) if len(pts) >= 5 else None
    bands = len(set(round(i[0][1] * 2) / 2 for i in items))
    rr = "%.2f" % fit[1] if fit else "-"
    rms = "%.2f" % (fit[2] / fit[1]) if fit else "-"
    print("%-34s %-3s %4d %5.1f %5.1f %5.1f %6s %6s %5d" %
          (n[:34], side, len(items), r["w"], r["h"], r["d"], rr, rms, bands))

# ---------------------------------------------------------------- 法向贴合
print("\n=== 法向贴合度：每块最薄轴 vs 径向（球心=拟合中心）")
res = []
for r in big:
    n, side = r["model"], r["side"]
    s = by_model[n]["skin"]
    items = [(c, sz, ro) for c, sz, ro, rf in zip(s["centers"], s["sizes"], s["rots"], s["rotflags"])
             if (c[0] > 0) == (side == "L")]
    pts = [i[0] for i in items]
    fit = H.fit_sphere(pts)
    if not fit or len(items) < 8:
        continue
    ctr = fit[0]
    angs = []
    for c, sz, ro in items:
        axes = H.rot_axes(*ro)
        thin = min(range(3), key=lambda i: sz[i])
        radial = H.norm((c[0] - ctr[0], c[1] - ctr[1], c[2] - ctr[2]))
        v = axes[thin]
        d = abs(sum(v[i] * radial[i] for i in range(3)))
        d = min(1.0, max(-1.0, d))
        angs.append(math.degrees(math.acos(d)))
    res.append({"model": n, "side": side, "n": len(items),
                "mean": st.mean(angs), "median": st.median(angs),
                "p75": H.q(angs, 0.75)})
print("模型侧数", len(res))
print("  平均偏差角(deg)", H.stat([x["mean"] for x in res]))
print("  中位偏差角", H.stat([x["median"] for x in res]))
print("  p75 偏差角", H.stat([x["p75"] for x in res]))
for x in sorted(res, key=lambda x: -x["n"])[:14]:
    print("   %-34s %s n=%-3d mean=%.0f° med=%.0f° p75=%.0f°" %
          (x["model"][:34], x["side"], x["n"], x["mean"], x["median"], x["p75"]))

# ---------------------------------------------------------------- 衣服版
print("\n=== 衣服版胸（bones 名含 cloth/bra/armor...）厚度明细")
cl = [(r["model"], r["cloth"]) for r in rows if r["cloth"]]
cl.sort(key=lambda x: -x[1]["n"])
print("%-40s %-40s %4s %6s %6s %6s %6s" % ("model", "bones", "n", "thick", "mid", "long", "rot%"))
for m, c in cl[:28]:
    print("%-40s %-40s %4d %6.2f %6.2f %6.2f %6.0f" %
          (m[:40], ",".join(c["bones"])[:40], c["n"], c["thick_med"], c["mid_med"],
           c["long_med"], 100 * c["rot_frac"]))
print("cloth thick 分布", H.stat([c["thick_med"] for _, c in cl]))
print("cloth 中 <0.4 的模型数", sum(1 for _, c in cl if c["thick_med"] < 0.4), "/", len(cl))

# ---------------------------------------------------------------- 低块数（廉价做法）
print("\n=== 低块数样本（1-4 块）的做法")
low = [r for r in rows if r["skin"] and r["skin"]["n"] <= 4]
print("模型数", len(low))
for r in low[:14]:
    s = r["skin"]
    cs = [(c, sz, ro) for c, sz, ro, rf in zip(s["centers"], s["sizes"], s["rots"], s["rotflags"])]
    print("  %-32s n=%d bones=%s" % (r["model"][:32], s["n"], ",".join(s["bones"])[:40]))
    for c, sz, ro in cs[:4]:
        print("      size=%-16s rot=%-22s c=%s" % (sz, ro, c))
