"""Build a contact sheet from image paths.

Usage: python montage.py --out OUT.png --cell 700 --cols 3 a.png b.png ...
"""
import argparse
import os

from PIL import Image


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--cell", type=int, default=700)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--bg", default="#202020")
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()

    cell = args.cell
    cols = args.cols
    rows = (len(args.paths) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), args.bg)
    for i, p in enumerate(args.paths):
        im = Image.open(p).convert("RGBA")
        im.thumbnail((cell, cell), Image.LANCZOS)
        tile = Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
        tile.paste(im, ((cell - im.width) // 2, (cell - im.height) // 2), im)
        sheet.paste(tile, ((i % cols) * cell, (i // cols) * cell), tile)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    sheet.save(args.out)
    print("%s  %dx%d  (%d tiles)" % (args.out, sheet.width, sheet.height, len(args.paths)))


if __name__ == "__main__":
    main()
