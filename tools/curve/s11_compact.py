#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""紧凑打印多个模型的躯干剖面（归一化高度）。"""
import json
import sys

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

C = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_chain.json", encoding="utf-8"))


def compact(n, nb=14):
    d = C[n]
    fb = d["foot_bottom"]
    top = d["head"]["top"]
    Ht = top - fb
    leg_y = d["leg_y"] or fb
    arm_y = d["arm_y"]
    prof = {float(k): v for k, v in d["profile"].items()}
    ys = sorted(prof)
    print("-" * 78)
    print("%s  H=%.1f headH=%.1f segs=%d torsoCubes=%d rot=%.2f" %
          (n, Ht, d["head"]["h"], d["n_torso_bones"], d["n_torso_cubes"], d["rot_frac"]))
    print("  segs: " + " | ".join("%s %.1fw %dc" % (s["name"], s["w"], s["n"]) for s in d["segs"]))
    line = []
    for i in range(nb):
        t = leg_y + (arm_y - leg_y) * i / (nb - 1)
        k = min(ys, key=lambda x: abs(x - t))
        line.append("%.1f" % prof[k]["w"])
    print("  torso w @t=0..1 (legPivot→armPivot): " + " ".join(line))
    line = []
    for i in range(nb):
        t = fb + (top - fb) * i / (nb - 1)
        k = min(ys, key=lambda x: abs(x - t))
        line.append("%.1f" % prof[k]["w"] if abs(k - t) < 6 else "--")
    print("  whole  w @t=0..1 (foot→headtop):     " + " ".join(line))
    # 全模型（含裙）中线剖面
    P = json.load(open(r"F:\Deepseek_harness\blockbench\tools\curve\out_profile.json", encoding="utf-8"))
    if n in P:
        pr = {float(k): v for k, v in P[n]["profile"].items()}
        keys = sorted(pr)
        line = []
        for i in range(nb):
            t = fb + (top - fb) * i / (nb - 1)
            k = min(keys, key=lambda x: abs(x - t))
            line.append("%.1f" % pr[k]["w"])
        print("  full   w @t=0..1 (foot→headtop):     " + " ".join(line))


for n in ["hi3_elysia__ae12017978c2", "hsr_jingliu__d803a5536723", "nvshi__ee8cadc8a57a",
          "zhe_1__b0cffdb26058", "jizi__2c90d16c1e70", "gs_qz_yg__78b9dcf3d436",
          "bronya_reason4.2__7e7ed02b87cc", "ruanmei__20d0917bb915"]:
    if n in C:
        compact(n)
