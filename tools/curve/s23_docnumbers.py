#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把要写进文档的关键数字集中打印一遍（防止抄错）。"""
import json
import statistics as st
import sys

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
B = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_breast.json", encoding="utf-8"))
B2 = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_breast2.json", encoding="utf-8"))
C = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_chain.json", encoding="utf-8"))
W = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_waist.json", encoding="utf-8"))
L = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_last.json", encoding="utf-8"))
BG = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_bulge.json", encoding="utf-8"))

print("模型数", len(F))
print("总块数", H.stat([F[n]["n_cubes"] for n in F]))
print("\n胸：A组 h/H<0.28 =", len(B2["A"]), " B组 =", len(B2["B"]))
print("A组块数", H.stat([x["n"] for x in B2["A"]]))
print("A组>=20块", H.stat([x["n"] for x in B2["A"] if x["n"] >= 20]))
print("A组厚度", H.stat([x["thick"] for x in B2["A"]]))
print("A组长度", H.stat([x["long"] for x in B2["A"]]))
print("A组h/H", H.stat([x["h_rel"] for x in B2["A"]]))
print("A组w/H", H.stat([x["w_rel"] for x in B2["A"]]))
print("A组d/H", H.stat([x["d_rel"] for x in B2["A"]]))
print("A组t", H.stat([x["t"] for x in B2["A"] if x["t"] is not None]))
print("胸前突", H.stat([x["bulge"] for x in BG]), " 明显者",
      H.stat([x["bulge"] for x in BG if x["bulge"] > 1]))
print("前突峰值t", H.stat([x["t"] for x in BG if x["bulge"] > 1]))
print("\n腰：pinch %d/%d" % (sum(1 for r in W if r["pinch"]), len(W)))
print("pinch depth", H.stat([r["depth"] for r in W if r["pinch"]]))
print("t_waist", H.stat([r["t_waist"] for r in W if r["pinch"]]))
print("waist_hip", H.stat([r["waist_hip"] for r in W]))
print("waist_bust", H.stat([r["waist_bust"] for r in W]))
print("hip_bust", H.stat([r["hip_bust"] for r in W]))
print("\n躯干段分布", {k: sum(1 for n in C if len([s for s in C[n]["segs"] if s["n"] > 0]) == k)
                   for k in (1, 2, 3, 4, 6)})
print("躯干块数", H.stat([C[n]["n_torso_cubes"] for n in C]))
print("躯干旋转占比", H.stat([C[n]["rot_frac"] for n in C]))
print("\n腿：", H.stat([r["n"] for r in L["legs"]]))
print("腿宽", {k: H.stat([r[k] for r in L["legs"]]) for k in ("w_thigh", "w_knee", "w_calf", "w_ankle")})
print("\n头身比(原始)", H.stat([p["ratio"] for p in L["props"] if p["ratio"]]))
trim = [p["ratio"] for p in L["props"] if p["ratio"] and 3 <= p["ratio"] <= 8]
print("头身比(3-8)", H.stat(trim))
print("腿长占比", H.stat([p["leg_share"] for p in L["props"] if p["leg_share"]]))
print("肩枢轴/胯枢轴", H.stat([2 * p["arm_x"] / (2 * p["leg_x"]) for p in L["props"]
                            if p["arm_x"] and p["leg_x"]]))
