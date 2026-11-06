#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把超长教程截图切成 OCR 可处理的横条。

用法: python tools/slice_longimg.py --in <png> --outdir <dir> [--height 1200] [--overlap 120]
"""
from __future__ import annotations

import argparse
import os
import sys

from PIL import Image


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--height", type=int, default=1200)
    ap.add_argument("--overlap", type=int, default=120)
    ap.add_argument("--scale", type=float, default=1.0, help="放大倍数，小字时可设 1.5-2")
    args = ap.parse_args()

    if not os.path.isfile(args.src):
        print(f"not found: {args.src}", file=sys.stderr)
        return 2
    os.makedirs(args.outdir, exist_ok=True)

    im = Image.open(args.src).convert("RGB")
    W, H = im.size
    if args.scale != 1.0:
        W2, H2 = int(W * args.scale), int(H * args.scale)
        im = im.resize((W2, H2), Image.LANCZOS)
        W, H = im.size

    step = max(1, args.height - args.overlap)
    n = 0
    y = 0
    while y < H:
        y2 = min(H, y + args.height)
        crop = im.crop((0, y, W, y2))
        # 记录该条的绝对 y 偏移，写进文件名
        crop.save(os.path.join(args.outdir, f"strip_{y:06d}.png"))
        n += 1
        if y2 >= H:
            break
        y += step
    print(f"{os.path.basename(args.src)}: {im.size} -> {n} strips in {args.outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
