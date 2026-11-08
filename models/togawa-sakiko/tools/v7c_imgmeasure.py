import sys
import numpy as np
from PIL import Image

def load(p):
    a = np.array(Image.open(p).convert("RGBA")).astype(int)
    al = a[:, :, 3]
    if al.min() < 250:
        m = al > 16
    else:
        rgb = a[:, :, :3]
        m = np.abs(rgb - rgb[0, 0]).max(axis=2) > 12
    return a, m

def report(p, label):
    a, m = load(p)
    h, w = m.shape
    rows = np.where(m.any(axis=1))[0]
    cols = np.where(m.any(axis=0))[0]
    sc = (rows.max() - rows.min()) / 43.1743  # px per unit
    print(f"== {label} {p}")
    print(f"  bbox rows {rows.min()}..{rows.max()} cols {cols.min()}..{cols.max()} scale {sc:.2f} px/unit")
    rgb = a[:, :, :3]
    mx = rgb.max(axis=2); mn = rgb.min(axis=2)
    white = m & (mx > 195) & ((mx - mn) < 30)
    blue = m & (rgb[:, :, 2] > rgb[:, :, 0] + 25) & (rgb[:, :, 2] > 80) & (rgb[:, :, 2] < 230)
    # boots: bottom 12% of model
    lo = int(rows.min() + 0.88 * (rows.max() - rows.min()))
    boots = m[lo:rows.max() + 1]
    cs = np.where(boots.any(axis=0))[0]
    print(f"  boots band rows {lo}..{rows.max()} x {cs.min()}..{cs.max()} center {(cs.min()+cs.max())/2:.1f}")
    bodyc = (cs.min() + cs.max()) / 2
    for nm, mask in (("white", white), ("blue", blue)):
        ys, xs = np.where(mask)
        if len(xs) < 30:
            print(f"  {nm}: none"); continue
        # keep only the skirt band (below 45% of model height)
        sel = ys > rows.min() + 0.45 * (rows.max() - rows.min())
        if sel.sum() < 30:
            print(f"  {nm}: none in skirt band"); continue
        ys2, xs2 = ys[sel], xs[sel]
        print(f"  {nm}: rows {ys2.min()}..{ys2.max()} x {xs2.min()}..{xs2.max()} center {(xs2.min()+xs2.max())/2:.1f} "
              f"dx_vs_body {((xs2.min()+xs2.max())/2 - bodyc)/sc:+.2f}u  hemY {(rows.max()-ys2.max())/sc:.2f}u above floor")
    # hem edge per column (bottom-most skirt pixel) for blue+white+black in skirt band
    band_lo = int(rows.min() + 0.45 * (rows.max() - rows.min()))
    cols_lo, cols_hi = cols.min(), cols.max()
    print("  hem profile (col -> bottom row, units above floor):")
    for frac in (0.08, 0.2, 0.35, 0.5, 0.65, 0.8, 0.92):
        c = int(cols_lo + frac * (cols_hi - cols_lo))
        rr = np.where(m[band_lo:, c])[0]
        if len(rr):
            print(f"    x={c:5d} ({frac:.2f}) bottom row {band_lo+rr.max():5d} -> {(rows.max()-(band_lo+rr.max()))/sc:5.2f}u")
    # hole test inside skirt band
    holes = 0
    tot = 0
    for y in range(band_lo, rows.max()):
        xs = np.where(m[y])[0]
        if len(xs) < 4:
            continue
        tot += 1
        seg = m[y, xs.min():xs.max() + 1]
        if (~seg).sum() > 0:
            holes += int((~seg).sum())
    print(f"  interior background pixels in skirt band: {holes} (rows {tot})")

for p, lab in [(sys.argv[1], "view1"), (sys.argv[2], "view2")]:
    report(p, lab)
