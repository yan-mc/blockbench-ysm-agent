#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正交轮廓图 v2：只画身体（跳过头发/披风/武器），按 z 从后往前排序，
躯干/胸/腿/裙分组上色。"""
import json
import sys
from PIL import Image, ImageDraw

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()
SKIP = (H.RE_HAIR, H.RE_CAPE, H.RE_WEAPON)


def group(name):
    low = name.lower()
    if H.RE_BREAST.search(low):
        return (225, 55, 70)
    if H.is_skirt(low):
        return (225, 190, 50)
    if H.RE_FOOT.search(low):
        return (45, 170, 100)
    if H.RE_LEG_LOW.search(low) or H.RE_LEG_UP.search(low):
        return (35, 140, 70)
    if H.RE_TORSO_LOOSE.search(low) or H.RE_PELVIS.search(low):
        return (65, 115, 215)
    if H.RE_HAND.search(low):
        return (90, 200, 220)
    if H.RE_ARM.search(low):
        return (125, 165, 235)
    if H.RE_HEAD.search(low):
        return (240, 222, 190)
    return (170, 170, 178)


def render(n, view="front", scale=4, out=None, pad=3):
    cs = [c for c in F[n]["cubes"] if not any(r.search(c["b"].lower()) for r in SKIP)]
    if not cs:
        return None
    xs0 = min(c["bb"][0] for c in cs)
    xs1 = max(c["bb"][3] for c in cs)
    ys0 = min(c["bb"][1] for c in cs)
    ys1 = max(c["bb"][4] for c in cs)
    zs0 = min(c["bb"][2] for c in cs)
    zs1 = max(c["bb"][5] for c in cs)
    a0, a1 = (xs0, xs1) if view == "front" else (zs0, zs1)
    W = int((a1 - a0) * scale) + 2 * pad
    Hh = int((ys1 - ys0) * scale) + 2 * pad
    im = Image.new("RGB", (W, Hh), (22, 22, 26))
    dr = ImageDraw.Draw(im)

    def px(a, y):
        return (pad + (a - a0) * scale, pad + (ys1 - y) * scale)

    # 后→前
    key = (lambda c: -c["bb"][5]) if view == "front" else (lambda c: -c["bb"][3])
    for c in sorted(cs, key=key):
        bb = c["bb"]
        col = group(c["b"])
        if view == "front":
            p0 = px(bb[0], bb[4])
            p1 = px(bb[3], bb[1])
        else:
            p0 = px(bb[2], bb[4])
            p1 = px(bb[5], bb[1])
        dr.rectangle([p0[0], p0[1], max(p0[0] + 1, p1[0]), max(p0[1] + 1, p1[1])],
                     fill=col)
    if out:
        im.save(out)
    return im


if __name__ == "__main__":
    for n in sys.argv[1:]:
        for v in ("front", "side"):
            out = r"F:\Deepseek_harness\blockbench\tools\curve\sil2_%s_%s.png" % (n.split("__")[0], v)
            render(n, v, 4, out)
            print("wrote", out)
