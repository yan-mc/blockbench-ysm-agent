#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正交前视/侧视轮廓图：验证测量（不是渲染，只是方块投影上色）。
分组着色：躯干蓝 / 胸红 / 腿绿 / 裙黄 / 头发灰 / 其余浅灰。
"""
import json
import sys
from PIL import Image, ImageDraw

sys.path.insert(0, r"F:\Deepseek_harness\blockbench\tools\curve")
import helpers as H

F = H.load()


def group(name):
    low = name.lower()
    if H.RE_BREAST.search(low):
        return (220, 40, 60)
    if H.is_hair(low):
        return (150, 150, 150)
    if H.is_skirt(low):
        return (230, 190, 40)
    if H.RE_FOOT.search(low):
        return (40, 160, 90)
    if H.RE_LEG_LOW.search(low) or H.RE_LEG_UP.search(low):
        return (30, 130, 60)
    if H.RE_TORSO_LOOSE.search(low) or H.RE_PELVIS.search(low):
        return (60, 110, 210)
    if H.RE_ARM.search(low):
        return (120, 160, 230)
    if H.RE_HAND.search(low):
        return (90, 200, 220)
    if H.RE_HEAD.search(low):
        return (240, 220, 190)
    return (185, 185, 185)


def render(n, view="front", scale=4, out=None, pad=2):
    cs = F[n]["cubes"]
    if not cs:
        return None
    xs0 = min(c["bb"][0] for c in cs)
    xs1 = max(c["bb"][3] for c in cs)
    ys0 = min(c["bb"][1] for c in cs)
    ys1 = max(c["bb"][4] for c in cs)
    zs0 = min(c["bb"][2] for c in cs)
    zs1 = max(c["bb"][5] for c in cs)
    if view == "front":
        a0, a1 = xs0, xs1
        b0, b1 = ys0, ys1
    else:
        a0, a1 = zs0, zs1
        b0, b1 = ys0, ys1
    W = int((a1 - a0) * scale) + 2 * pad
    Hh = int((b1 - b0) * scale) + 2 * pad
    im = Image.new("RGB", (W, Hh), (24, 24, 28))
    dr = ImageDraw.Draw(im)

    def px(x, y):
        return (pad + (x - a0) * scale, pad + (b1 - y) * scale)

    for c in sorted(cs, key=lambda c: c["bb"][5] if view == "front" else c["bb"][3]):
        col = group(c["b"])
        bb = c["bb"]
        if view == "front":
            p0 = px(bb[0], bb[4])
            p1 = px(bb[3], bb[1])
        else:
            p0 = px(bb[2], bb[4])
            p1 = px(bb[5], bb[1])
        dr.rectangle([p0[0], p0[1], max(p0[0] + 1, p1[0]), max(p0[1] + 1, p1[1])], fill=col,
                     outline=(0, 0, 0))
    if out:
        im.save(out)
    return im


if __name__ == "__main__":
    for n in sys.argv[1:]:
        for v in ("front", "side"):
            out = r"F:\Deepseek_harness\blockbench\tools\curve\sil_%s_%s.png" % (n.split("__")[0], v)
            render(n, v, 4, out)
            print("wrote", out)
