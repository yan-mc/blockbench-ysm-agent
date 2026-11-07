import os
from PIL import Image

ROOT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
REND = os.path.join(ROOT, "artifacts", "renders", "r0019")
OUT = os.path.join(ROOT, "artifacts", "v5", "final")
os.makedirs(OUT, exist_ok=True)


def skin_bbox(im):
    w, h = im.size
    px = im.load()
    minx, miny, maxx, maxy = w, h, -1, -1
    n = 0
    for y in range(250, 3400, 2):
        for x in range(1400, 3400, 2):
            r, g, b, a = px[x, y]
            if a > 200 and 165 <= r <= 245 and 145 <= g <= 220 and 145 <= b <= 220 \
                    and 8 <= (r - b) <= 45 and 6 <= (r - g) <= 35:
                n += 1
                minx = min(minx, x); maxx = max(maxx, x)
                miny = min(miny, y); maxy = max(maxy, y)
    return (minx, miny, maxx, maxy) if n > 100 else None, n


def crop_center(im, cx, cy, size):
    w, h = im.size
    x0 = max(0, min(w - size, int(round(cx - size / 2))))
    y0 = max(0, min(h - size, int(round(cy - size / 2))))
    return im.crop((x0, y0, x0 + size, y0 + size)), (x0, y0)


def main():
    # front: center on detected face skin
    im = Image.open(os.path.join(REND, "front_4800.png")).convert("RGBA")
    sb, n = skin_bbox(im)
    print("front skin_bbox", sb, "n", n)
    assert sb
    fcx = (sb[0] + sb[2]) / 2.0
    fcy = (sb[1] + sb[3]) / 2.0
    out, box = crop_center(im, fcx, fcy, 1600)
    out.save(os.path.join(OUT, "final-head-front-1600.png"))
    print("final-head-front-1600.png crop", box)

    # left: side profile is hair-covered; keep identical vertical framing
    im = Image.open(os.path.join(REND, "left_4800.png")).convert("RGBA")
    ab = im.getchannel("A").getbbox()
    print("left alpha_bbox", ab)
    lcx = (ab[0] + ab[2]) / 2.0
    out, box = crop_center(im, lcx, fcy, 1600)
    out.save(os.path.join(OUT, "final-head-left-1600.png"))
    print("final-head-left-1600.png crop", box)


if __name__ == "__main__":
    main()
