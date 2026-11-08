"""Crop a render to an alpha-bbox square and resize to target size.

Usage:
  python crop_final.py --in SRC.png --out DST.png --size 1600 [--region y0,y1] [--margin 0.04]
"""
import argparse
import os

from PIL import Image


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--size", type=int, default=1600)
    ap.add_argument("--region", default=None, help="y0,y1 fractions of height")
    ap.add_argument("--margin", type=float, default=0.04)
    args = ap.parse_args()

    im = Image.open(args.src).convert("RGBA")
    w, h = im.size
    y0, y1 = 0.0, 1.0
    if args.region:
        a, b = args.region.split(",")
        y0, y1 = float(a), float(b)
    top, bottom = int(round(y0 * h)), int(round(y1 * h))
    part = im.crop((0, top, w, bottom))
    bbox = part.getchannel("A").getbbox()
    if bbox is None:
        raise SystemExit("empty alpha region: %s" % args.src)
    x0, yy0, x1, yy1 = bbox
    yy0 += top
    yy1 += top
    bw, bh = x1 - x0, yy1 - yy0
    side = int(max(bw, bh) * (1 + 2 * args.margin))
    cx, cy = (x0 + x1) / 2.0, (yy0 + yy1) / 2.0
    left = int(round(cx - side / 2.0))
    upper = int(round(cy - side / 2.0))
    left = max(0, min(left, w - side)) if side <= w else 0
    upper = max(0, min(upper, h - side)) if side <= h else 0
    side = min(side, w, h)
    crop = im.crop((left, upper, left + side, upper + side))
    out = crop.resize((args.size, args.size), Image.LANCZOS)
    os.makedirs(os.path.dirname(args.dst), exist_ok=True)
    out.save(args.dst)
    print(
        "%s -> %s | src=%dx%d bbox=(%d,%d,%d,%d) side=%d crop=(%d,%d) out=%dx%d"
        % (
            os.path.basename(args.src),
            os.path.basename(args.dst),
            w,
            h,
            x0,
            yy0,
            x1,
            yy1,
            side,
            left,
            upper,
            out.size[0],
            out.size[1],
        )
    )


if __name__ == "__main__":
    main()
