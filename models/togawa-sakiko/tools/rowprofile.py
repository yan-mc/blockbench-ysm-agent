"""Print alpha row-span profile of a render (fractional y, x extents)."""
import sys

from PIL import Image


def main() -> None:
    path = sys.argv[1]
    step = float(sys.argv[2]) if len(sys.argv) > 2 else 0.02
    im = Image.open(path).convert("RGBA")
    a = im.getchannel("A")
    w, h = im.size
    y = 0.0
    while y < 1.0:
        row = a.crop((0, int(y * h), w, min(h, int((y + step) * h) + 1)))
        bb = row.getbbox()
        if bb is None:
            print("y=%.2f  ---" % y)
        else:
            print(
                "y=%.2f  x=[%.4f..%.4f] w=%.4f  h=%d"
                % (y, bb[0] / w, bb[2] / w, (bb[2] - bb[0]) / w, bb[3] - bb[1])
            )
        y += step


if __name__ == "__main__":
    main()
