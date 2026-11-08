import sys
import numpy as np
from PIL import Image

def load(p):
    a = np.array(Image.open(p).convert("RGBA")).astype(int)
    al = a[:, :, 3]
    m = (al > 16) if al.min() < 250 else (np.abs(a[:, :, :3] - a[0, 0, :3]).max(axis=2) > 12)
    return a, m

def hem_band(p, label, r0, r1):
    a, m = load(p)
    h, w = m.shape
    rows = np.where(m.any(axis=1))[0]
    sc = (rows.max() - rows.min()) / 43.1743
    rgb = a[:, :, :3]
    mx = rgb.max(axis=2); mn = rgb.min(axis=2)
    white = m & (mx > 195) & ((mx - mn) < 30)
    blue = m & (rgb[:, :, 2] > rgb[:, :, 0] + 25) & (rgb[:, :, 2] > 80) & (rgb[:, :, 2] < 235)
    print(f"== {label} (scale {sc:.2f} px/u, floor row {rows.max()})")
    for nm, mask in (("white", white), ("blue", blue)):
        sub = mask[r0:r1]
        ys, xs = np.where(sub)
        if len(xs) < 20:
            print(f"  {nm}: none in band"); continue
        ys = ys + r0
        print(f"  {nm}: rows {ys.min()}..{ys.max()} cols {xs.min()}..{xs.max()} center {(xs.min()+xs.max())/2:.1f} "
              f"width {(xs.max()-xs.min())/sc:.2f}u  bottomY {(rows.max()-ys.max())/sc:.2f}u")
    # silhouette bottom per column inside skirt x-range
    xsall = np.where(m[r0:r1].any(axis=0))[0]
    print("  bottom edge by column:")
    for f in (0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98):
        c = int(xsall.min() + f * (xsall.max() - xsall.min()))
        rr = np.where(m[r0:, c])[0]
        if len(rr):
            print(f"    f={f:.2f} col {c} bottom {(rows.max()-(r0+rr.max()))/sc:.2f}u")

def crop(p, out, box, scale=2):
    im = Image.open(p).convert("RGBA")
    c = im.crop(box)
    c = c.resize((c.width * scale, c.height * scale), Image.NEAREST)
    bg = Image.new("RGBA", c.size, (24, 24, 30, 255))
    bg.alpha_composite(c)
    bg.convert("RGB").save(out)
    print("wrote", out, c.size)

if __name__ == "__main__":
    hem_band(sys.argv[1], "front", 1180, 1420)
    hem_band(sys.argv[2], "left", 1180, 1420)
