#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""最终统计：头（去发）包围盒、肩宽、A-pose 角、轮廓宽比、腿长占比。写 out_final.json"""
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
P = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_profile.json", encoding="utf-8"))

SKIP = (H.RE_HAIR, H.RE_CAPE, H.RE_WEAPON)


def bmap(n):
    return {b["n"]: b for b in F[n]["bones"]}


def subtree(bm, root):
    out, stack = [], [root]
    while stack:
        cur = stack.pop()
        out.append(cur)
        for k, v in bm.items():
            if v.get("p") == cur:
                stack.append(k)
    return out


def head_bbox(n):
    """头子树（去掉头发/披风）的世界 bbox。"""
    bm = bmap(n)
    root = None
    for cand in ("allhead", "head"):
        for k in bm:
            if k.lower() == cand:
                root = k
                break
        if root:
            break
    if not root:
        return None
    names = [x for x in subtree(bm, root) if not any(r.search(x.lower()) for r in SKIP)]
    cs = [c for c in F[n]["cubes"] if c["b"] in names]
    if not cs:
        return None
    return {
        "w": max(c["bb"][3] for c in cs) - min(c["bb"][0] for c in cs),
        "h": max(c["bb"][4] for c in cs) - min(c["bb"][1] for c in cs),
        "top": max(c["bb"][4] for c in cs),
        "bot": min(c["bb"][1] for c in cs),
        "n": len(cs),
    }


def foot_bottom(n):
    ys = [b["bb"][1] for b in F[n]["bones"] if b["bb"] and H.RE_FOOT.search(b["n"].lower())]
    return min(ys) if ys else None


def arm_pose(n):
    bm = bmap(n)
    for k in bm:
        if k.lower() in ("leftarm", "rightarm"):
            r = bm[k]["rot"]
            return {"bone": k, "rot": r, "az": abs(r[2]), "ax": abs(r[0])}
    return None


def shoulder_w(n):
    bm = bmap(n)
    la = next((k for k in bm if k.lower() == "leftarm"), None)
    ra = next((k for k in bm if k.lower() == "rightarm"), None)
    if not la or not ra:
        return None
    lcs = [c for c in F[n]["cubes"] if c["b"] == la]
    rcs = [c for c in F[n]["cubes"] if c["b"] == ra]
    if not lcs or not rcs:
        return 2 * (abs(bm[la]["pivot"][0]) + abs(bm[ra]["pivot"][0])) / 2
    ytop = max(c["bb"][4] for c in lcs + rcs)
    band = [c for c in lcs if c["bb"][4] > ytop - 2.5] + [c for c in rcs if c["bb"][4] > ytop - 2.5]
    if not band:
        return None
    return max(c["bb"][3] for c in band) - min(c["bb"][0] for c in band)


def silhouette(n):
    """去发/披风后的中线剖面（x 宽）。返回 {y: w}"""
    pr = P.get(n)
    if not pr:
        return None
    return {float(k): v["w"] for k, v in pr["profile"].items()}


rows = []
for n in sorted(F):
    hb = head_bbox(n)
    fb = foot_bottom(n)
    if not hb or fb is None:
        continue
    Ht = hb["top"] - fb
    if Ht <= 5:
        continue
    bm = bmap(n)
    leg = next((b for b in bm if b.lower() == "leftleg"), None)
    leg_y = bm[leg]["pivot"][1] if leg else None
    arm = next((b for b in bm if b.lower() == "leftarm"), None)
    arm_y = bm[arm]["pivot"][1] if arm else None
    r = {
        "model": n, "H": round(Ht, 2), "head_h": round(hb["h"], 2), "head_w": round(hb["w"], 2),
        "head_top": round(hb["top"], 2), "foot_bottom": round(fb, 2),
        "head_ratio": round(Ht / hb["h"], 3) if hb["h"] else None,
        "head_share": round(hb["h"] / Ht, 3) if Ht else None,
        "leg_share": round((leg_y - fb) / Ht, 3) if leg_y else None,
        "leg_y": leg_y, "arm_y": arm_y,
        "shoulder_w": shoulder_w(n),
        "arm_pose": arm_pose(n),
        "cubes": F[n]["n_cubes"], "bones": F[n]["n_bones"],
    }
    r["shoulder_H"] = round(r["shoulder_w"] / Ht, 3) if r["shoulder_w"] else None
    r["shoulder_head"] = round(r["shoulder_w"] / hb["w"], 3) if r["shoulder_w"] and hb["w"] else None
    rows.append(r)

print("=== 头身比（头=去掉头发的头子树包围盒）")
print("  n =", len(rows))
print("  head_ratio", H.stat([r["head_ratio"] for r in rows if r["head_ratio"]]))
print("  head_share", H.stat([r["head_share"] for r in rows if r["head_share"]]))
b = Counter()
for r in rows:
    v = r["head_ratio"]
    if not v:
        continue
    k = ("<4.5" if v < 4.5 else "4.5-5" if v < 5 else "5-5.5" if v < 5.5 else
         "5.5-6" if v < 6 else "6-6.5" if v < 6.5 else "6.5-7" if v < 7 else "7-8" if v < 8 else ">=8")
    b[k] += 1
for k in ["<4.5", "4.5-5", "5-5.5", "5.5-6", "6-6.5", "6.5-7", "7-8", ">=8"]:
    print("     %-8s %d" % (k, b[k]))
print("\n=== 腿长占比")
print("  ", H.stat([r["leg_share"] for r in rows if r["leg_share"]]))
print("\n=== 肩宽")
print("  shoulder_w", H.stat([r["shoulder_w"] for r in rows if r["shoulder_w"]]))
print("  shoulder/H", H.stat([r["shoulder_H"] for r in rows if r["shoulder_H"]]))
print("  shoulder/head_w", H.stat([r["shoulder_head"] for r in rows if r["shoulder_head"]]))
print("\n=== A-pose 上臂外展角（|rotZ|）")
az = [r["arm_pose"]["az"] for r in rows if r["arm_pose"]]
print("  ", H.stat(az))
print("  0° 的模型", sum(1 for a in az if a < 1), "/", len(az))
print("  15-30° 的模型", sum(1 for a in az if 15 <= a <= 30))
print("  >30° 的模型", sum(1 for a in az if a > 30))

# ---- 轮廓宽比
print("\n=== 轮廓宽比（去发/披风的中线剖面，含衣物与裙）")
rat = []
broken = 0
for r in rows:
    pr = silhouette(r["model"])
    if not pr:
        continue
    ys = sorted(pr)
    if not ys:
        continue
    arm_y, leg_y = r["arm_y"], r["leg_y"]
    if not arm_y or not leg_y:
        continue
    def band(a, b_, mode="max"):
        v = [pr[y] for y in ys if a <= y <= b_]
        if not v:
            return None
        return max(v) if mode == "max" else min(v)
    bust = band(arm_y - 7, arm_y - 1)
    waist = band(leg_y + 2, arm_y - 6, "min")
    hip = band(leg_y - 4, leg_y + 2)
    if not (bust and waist and hip):
        continue
    if max(bust, waist, hip) > 1.6 * r["H"]:
        broken += 1
        continue
    rat.append({"model": r["model"], "bust": bust, "waist": waist, "hip": hip,
                "w_waist_bust": waist / bust, "w_waist_hip": waist / hip,
                "hip_bust": hip / bust,
                "waist_head": waist / r["head_w"], "hip_head": hip / r["head_w"],
                "shoulder_head": r["shoulder_head"], "H": r["H"], "head_w": r["head_w"]})
print("  可测", len(rat), " 剔除异常", broken)
for k in ("w_waist_bust", "w_waist_hip", "hip_bust"):
    v = [x[k] for x in rat]
    print("  %-12s %s" % (k, H.stat(v)))
    print("       <0.90: %.0f%%   <1.00: %.0f%%" %
          (100 * sum(1 for x in v if x < 0.9) / len(v), 100 * sum(1 for x in v if x < 1.0) / len(v)))
for k in ("waist_head", "hip_head"):
    print("  %-12s %s" % (k, H.stat([x[k] for x in rat])))
print("\n  最细腰（waist/bust 最小）:")
for x in sorted(rat, key=lambda x: x["w_waist_bust"])[:10]:
    print("    %-34s bust=%.1f waist=%.1f hip=%.1f  wa/bu=%.2f wa/hip=%.2f" %
          (x["model"][:34], x["bust"], x["waist"], x["hip"], x["w_waist_bust"], x["w_waist_hip"]))
print("  最不收腰:")
for x in sorted(rat, key=lambda x: -x["w_waist_bust"])[:6]:
    print("    %-34s bust=%.1f waist=%.1f hip=%.1f  wa/bu=%.2f wa/hip=%.2f" %
          (x["model"][:34], x["bust"], x["waist"], x["hip"], x["w_waist_bust"], x["w_waist_hip"]))

with open(r"F:\Deepseek_harness\blockbench\tools\curve\out_final.json", "w", encoding="utf-8") as f:
    json.dump({"props": rows, "ratios": rat}, f, ensure_ascii=False)
print("\nwrote out_final.json")
