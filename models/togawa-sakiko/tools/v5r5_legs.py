from PIL import Image
import numpy as np

p = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\renders\r0009\back_800.png"
im = Image.open(p).convert("RGB")
a = np.array(im).astype(int)
print(im.size)
# non-background = not near-white
bg = (a[:, :, 0] > 245) & (a[:, :, 1] > 245) & (a[:, :, 2] > 245)
fg = ~bg
cols = np.where(fg.any(axis=0))[0]
rows = np.where(fg.any(axis=1))[0]
print("fg bbox x", cols.min(), cols.max(), "y", rows.min(), rows.max())

crop = im.crop((330, 480, 600, 760)).resize((540, 560), Image.LANCZOS)
crop.save(r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\v5\r5\_legs_zoom.png")

# row scan: list runs of non-bg colors at several y
for y in (560, 600, 640, 680, 720):
    row = fg[y]
    xs = np.where(row)[0]
    if not len(xs):
        print(y, "empty"); continue
    # find contiguous runs
    runs = []
    s = xs[0]; prev = xs[0]
    for x in xs[1:]:
        if x != prev + 1:
            runs.append((s, prev)); s = x
        prev = x
    runs.append((s, prev))
    print(y, "runs", runs)
