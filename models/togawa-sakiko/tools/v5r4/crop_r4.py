# -*- coding: utf-8 -*-
"""Crop head / skirt / back-hair closeups out of a 1800^2 view render."""
import os, sys
from PIL import Image

R = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\renders\r0016"
OUT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\v5\r4"
os.makedirs(OUT, exist_ok=True)

TOP, BOT, SCALE, CX = 117.0, 1681.0, (1681.0 - 117.0) / 43.17, 899.5


def v(y):
    return int(TOP + (43.17 - y) * SCALE)


def u(x):
    return int(CX + x * SCALE)


jobs = [
    ("front_1800.png", "c-head-front", (-6.2, 6.2, 31.6, 43.4), 2.4),
    ("left_1800.png", "c-head-left", (-7.0, 7.0, 31.6, 43.4), 2.4),
    ("back_1800.png", "c-head-back", (-6.2, 6.2, 31.6, 43.4), 2.4),
    ("front_1800.png", "c-skirt-front", (-6.4, 6.4, 12.5, 25.0), 2.2),
    ("back_1800.png", "c-hair-back", (-6.5, 6.5, 24.0, 42.0), 2.0),
    ("left_1800.png", "c-body-left", (-8.0, 8.0, 10.0, 43.4), 1.5),
]
for src, name, (x0, x1, y0, y1), z in jobs:
    im = Image.open(os.path.join(R, src)).convert("RGB")
    box = (u(x0), v(y1), u(x1), v(y0))
    c = im.crop(box)
    c = c.resize((int(c.width * z), int(c.height * z)), Image.NEAREST)
    p = os.path.join(OUT, name + ".png")
    c.save(p)
    print(name, c.size, p)
