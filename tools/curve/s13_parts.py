#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q3–Q7 一次性统计：腿/臀/肩颈/手/整体比例。输出 out_parts.json + 屏幕报告。"""
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
P = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_profile.json", encoding="utf-8"))
C = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_chain.json", encoding="utf-8"))

LEG_UP = ("leftleg", "rightleg")
LEG_LO = ("leftlowerleg", "rightlowerleg")
FOOT = ("leftfoot", "rightfoot")


def bone(n, name):
    for b in F[n]["bones"]:
        if b["n"].lower() == name:
            return b
    return None


def cubes(n, names):
    s = {x.lower() for x in names}
    return [c for c in F[n]["cubes"] if c["b"].lower() in s]


def cluster_levels(vals, tol=0.75):
    if not vals:
        return []
    vs = sorted(vals)
    out = [[vs[0]]]
    for v in vs[1:]:
        if v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return out


def band_width(cs, band=1.0):
    if not cs:
        return {}
    lo = min(c["bb"][1] for c in cs)
    hi = max(c["bb"][4] for c in cs)
    out = {}
    k = 0
    y = lo
    while y < hi:
        sel = [c for c in cs if c["bb"][1] < y + band and c["bb"][4] > y]
        if sel:
            out[round(y, 1)] = {
                "w": max(c["bb"][3] for c in sel) - min(c["bb"][0] for c in sel),
                "d": max(c["bb"][5] for c in sel) - min(c["bb"][2] for c in sel),
            }
        y += band
        k += 1
        if k > 200:
            break
    return out


out = {}
for n in sorted(F):
    d = {"model": n, "cubes": F[n]["n_cubes"]}
    # ---- 腿
    for side in ("left", "right"):
        up = bone(n, side + "leg")
        lo = bone(n, side + "lowerleg")
        ft = bone(n, side + "foot")
        rec = {}
        for tag, b in (("thigh", up), ("calf", lo), ("foot", ft)):
            if not b:
                continue
            cs = [c for c in F[n]["cubes"] if c["b"] == b["n"]]
            rec[tag] = {
                "bone": b["n"], "n": len(cs),
                "sizes": [c["s"] for c in cs],
                "thick": round(st.median([min(c["s"]) for c in cs]), 2) if cs else None,
                "rot": round(sum(1 for c in cs if c["rot"]) / len(cs), 2) if cs else None,
                "levels": len(cluster_levels([c["c"][1] for c in cs])),
                "bb": [round(x, 2) for x in b["bb"]] if b["bb"] else None,
                "widths": band_width(cs) if cs else {},
            }
        d[side] = rec
    out[n] = d

# ---------------------------------------------------------------- 报告
print("=== Q3 腿：每侧块数")
for tag in ("thigh", "calf", "foot"):
    v = [out[n]["left"].get(tag, {}).get("n") for n in out if out[n]["left"].get(tag)]
    print("  %-6s %s" % (tag, H.stat(v)))
tot = []
for n in out:
    l, r = out[n]["left"], out[n]["right"]
    s = sum(x.get("n", 0) for x in (l.get("thigh"), l.get("calf"), l.get("foot")) if x)
    tot.append(s)
print("  单侧合计", H.stat(tot))

print("\n=== 腿的层级（环数）")
for tag in ("thigh", "calf"):
    v = [out[n]["left"][tag]["levels"] for n in out if out[n].get("left", {}).get(tag)]
    print("  %-6s %s" % (tag, H.stat(v)))
print("\n=== 腿的旋转占比")
for tag in ("thigh", "calf", "foot"):
    v = [out[n]["left"][tag]["rot"] for n in out if out[n].get("left", {}).get(tag)]
    print("  %-6s %s" % (tag, H.stat(v)))
print("\n=== 腿的板厚（最短边中位）")
for tag in ("thigh", "calf", "foot"):
    v = [out[n]["left"][tag]["thick"] for n in out if out[n].get("left", {}).get(tag)]
    print("  %-6s %s" % (tag, H.stat(v)))

print("\n=== 高细节腿样本（thigh 块数 top）")
top = sorted([n for n in out if out[n]["left"].get("thigh")],
             key=lambda n: -out[n]["left"]["thigh"]["n"])[:8]
for n in top:
    L = out[n]["left"]
    print("  %-34s thigh %3d 块 / %2d 环  calf %3d 块 / %2d 环  foot %3d" %
          (n[:34], L["thigh"]["n"], L["thigh"]["levels"],
           L["calf"]["n"] if L.get("calf") else -1,
           L["calf"]["levels"] if L.get("calf") else -1,
           L["foot"]["n"] if L.get("foot") else -1))
    ws = L["thigh"]["widths"]
    keys = sorted(float(k) for k in ws)
    print("     thigh 宽度序列: " + " ".join("%.1f" % ws[str(k) if str(k) in ws else k]["w"] for k in keys[:14]))
    if L.get("calf"):
        ws = L["calf"]["widths"]
        keys = sorted(float(k) for k in ws)
        print("     calf  宽度序列: " + " ".join("%.1f" % ws[str(k) if str(k) in ws else k]["w"] for k in keys[:14]))

# ---------------------------------------------------------------- Q4 臀
print("\n=== Q4 臀/胯：骨名")
cnt = Counter()
cubes_cnt = Counter()
for n in F:
    for b in F[n]["bones"]:
        if H.RE_PELVIS.search(b["n"].lower()):
            cnt[b["n"].lower()] += 1
            cubes_cnt[b["n"].lower()] += b["cc"]
for k, v in cnt.most_common(14):
    print("   %-24s models=%-3d cubes=%d" % (k, v, cubes_cnt[k]))
models_with_pelvis = sum(1 for n in F if any(H.RE_PELVIS.search(b["n"].lower()) and b["cc"] > 0
                                            for b in F[n]["bones"]))
print("  有专门臀/胯骨且带块:", models_with_pelvis, "/", len(F))

print("\n=== 裙：挂点与顶部高度相对胯")
skirt_models = 0
gap = []
for n in F:
    sk = [b for b in F[n]["bones"] if H.RE_SKIRT.search(b["n"].lower()) and b["cc"] > 0]
    if not sk:
        continue
    skirt_models += 1
    leg = bone(n, "leftleg")
    if not leg:
        continue
    top = max(b["bb"][4] for b in sk)
    gap.append((n, top - leg["pivot"][1]))
print("  有裙类骨且带块:", skirt_models)
print("  裙顶 y - 腿枢轴 y:", H.stat([g for _, g in gap]))
print("  >2（盖过胯）的比例: %.0f%%" % (100 * sum(1 for _, g in gap if g > 2) / max(1, len(gap))))

# ---------------------------------------------------------------- Q5 肩颈
print("\n=== Q5 肩/颈")
sh = Counter()
for n in F:
    for b in F[n]["bones"]:
        low = b["n"].lower()
        if H.RE_NECK.search(low):
            sh["neck:" + low] += 1
x = Counter()
for n in F:
    for b in F[n]["bones"]:
        low = b["n"].lower()
        if any(k in low for k in ("shoulder", "collar", "clavicle")):
            x[low] += 1
print("  肩/领骨 top:")
for k, v in x.most_common(8):
    print("   %-26s %d" % (k, v))
arm_x = []
neck_gap = []
for n in F:
    la, ra = bone(n, "leftarm"), bone(n, "rightarm")
    if la and ra:
        arm_x.append(la["pivot"][0] - ra["pivot"][0])
print("  左右臂枢轴间距:", H.stat(arm_x))
# 斜肩：手臂顶点 y vs 头底 y；肩是否低于颈根
slope = []
for n in F:
    la = bone(n, "leftarm")
    hd = bone(n, "head") or bone(n, "allhead")
    if not la or not hd or not la["bb"] or not hd["bb"]:
        continue
    slope.append((n, la["bb"][4] - hd["bb"][1]))
print("  臂顶 y - 头底 y:", H.stat([s for _, s in slope]))

# ---------------------------------------------------------------- Q6 手
print("\n=== Q6 手")
hand_n = []
finger_models = []
for n in F:
    hs = [b for b in F[n]["bones"] if b["n"].lower() in ("lefthand", "righthand", "hand")]
    if not hs:
        continue
    hand_n.append(sum(b["cc"] for b in hs))
    fg = [b for b in F[n]["bones"] if "finger" in b["n"].lower() and b["cc"] > 0]
    if fg:
        finger_models.append((n, len(fg), sum(b["cc"] for b in fg)))
print("  有 hand 骨的模型:", len(hand_n), " 块数", H.stat(hand_n))
print("  有手指骨的模型:", len(finger_models))
for x in sorted(finger_models, key=lambda r: -r[2])[:8]:
    print("   %-36s 手指骨 %d 块 %d" % (x[0][:36], x[1], x[2]))
glove = sum(1 for n in F if any("glove" in b["n"].lower() or
                                ("cloth" in b["n"].lower() and "hand" in b["n"].lower())
                                for b in F[n]["bones"]))
print("  有手套类骨的模型:", glove)

# ---------------------------------------------------------------- Q7 比例
print("\n=== Q7 整体比例（156 个可测模型）")
rows = []
for n, d in P.items():
    hm, fb = d["head"], d["foot_bottom"]
    pv = d["pivots"]
    top = hm["top"]
    Ht = top - fb
    if Ht <= 0:
        continue
    r = {"model": n, "H": Ht, "head_h": hm["h"], "head_w": hm["w"],
         "ratio": Ht / hm["h"] if hm["h"] else None,
         "leg": (pv.get("leg_y", 0) - fb) / Ht if pv.get("leg_y") else None,
         "legshare": (pv.get("leg_y", 0) - fb) / Ht if pv.get("leg_y") else None,
         "armx": pv.get("arm_x"), "legx": pv.get("leg_x"),
         "head_w_H": hm["w"] / Ht,
         }
    rows.append(r)
for k in ("ratio", "legshare", "head_w_H"):
    print("  %-10s %s" % (k, H.stat([r[k] for r in rows if r[k]])))
print("  头身比分布桶:")
b = Counter()
for r in rows:
    v = r["ratio"]
    if not v:
        continue
    k = ("<5" if v < 5 else "5-5.5" if v < 5.5 else "5.5-6" if v < 6 else
         "6-6.5" if v < 6.5 else "6.5-7" if v < 7 else "7-8" if v < 8 else ">=8")
    b[k] += 1
for k in ["<5", "5-5.5", "5.5-6", "6-6.5", "6.5-7", "7-8", ">=8"]:
    print("     %-8s %d" % (k, b[k]))
print("  leg share 桶:")
b = Counter()
for r in rows:
    v = r["legshare"]
    if v is None:
        continue
    k = ("<0.45" if v < 0.45 else "0.45-0.5" if v < 0.5 else "0.5-0.55" if v < 0.55
         else "0.55-0.6" if v < 0.6 else ">=0.6")
    b[k] += 1
for k in ["<0.45", "0.45-0.5", "0.5-0.55", "0.55-0.6", ">=0.6"]:
    print("     %-8s %d" % (k, b[k]))

with open(r"F:\Deepseek_harness\blockbench\tools\curve\out_parts.json", "w", encoding="utf-8") as f:
    json.dump({"legs": out, "props": rows}, f, ensure_ascii=False)
print("\nwrote out_parts.json")
