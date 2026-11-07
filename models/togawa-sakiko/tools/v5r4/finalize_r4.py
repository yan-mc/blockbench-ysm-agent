# -*- coding: utf-8 -*-
"""Final r4 deliverables: copy 4x2400 views, make head closeups."""
import os
from PIL import Image

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
R = os.path.join(ROOT, "artifacts", "renders", "r0019")
OUT = os.path.join(ROOT, "artifacts", "v5", "r4")
os.makedirs(OUT, exist_ok=True)

for src, dst in (("front_2400.png", "phase4-front-2400.png"),
                 ("left_2400.png", "phase4-left-2400.png"),
                 ("back_2400.png", "phase4-back-2400.png"),
                 ("iso_fr_2400.png", "phase4-iso-2400.png")):
    im = Image.open(os.path.join(R, src))
    im.save(os.path.join(OUT, dst))
    print(dst, im.size)

SCALE = (0.9346 - 0.065) * 2400 / 43.17
TOP = 0.065 * 2400
CX = (0.3275 + 0.6721) / 2 * 2400


def u(x):
    return int(CX + x * SCALE)


def v(y):
    return int(TOP + (43.17 - y) * SCALE)


jobs = [("front_2400.png", "phase4-head-front-1600.png", (-6.4, 6.4, 31.2, 43.5), 2.0),
        ("left_2400.png", "phase4-head-left-1600.png", (-7.6, 7.6, 31.2, 43.5), 2.0),
        ("back_2400.png", "phase4-hairback-1600.png", (-6.6, 6.6, 24.0, 43.0), 1.9)]
for src, dst, (x0, x1, y0, y1), z in jobs:
    im = Image.open(os.path.join(R, src)).convert("RGBA")
    c = im.crop((u(x0), v(y1), u(x1), v(y0)))
    c = c.resize((int(c.width * z), int(c.height * z)), Image.NEAREST)
    c.save(os.path.join(OUT, dst))
    print(dst, c.size)
