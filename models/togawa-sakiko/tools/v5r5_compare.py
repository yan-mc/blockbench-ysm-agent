from PIL import Image
import os

ref = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\refstudy"
ren = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\renders\r0009"
out_dir = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\v5\r5"
os.makedirs(out_dir, exist_ok=True)

pairs = [
    ("back", os.path.join(ref, "t3-panel5-back.png"), os.path.join(ren, "back_800.png")),
    ("side", os.path.join(ref, "t3-panel5-side.png"), os.path.join(ren, "right_800.png")),
]
H = 900
cells = []
for name, a, b in pairs:
    ia = Image.open(a).convert("RGB")
    ib = Image.open(b).convert("RGB")
    for im, label in ((ia, "T3 " + name), (ib, "v5 " + name)):
        s = H / im.height
        im2 = im.resize((max(1, int(im.width * s)), H), Image.LANCZOS)
        cells.append(im2)
W = sum(c.width for c in cells) + 12 * (len(cells) - 1)
out = Image.new("RGB", (W, H), (250, 250, 250))
x = 0
for c in cells:
    out.paste(c, (x, 0))
    x += c.width + 12
p = os.path.join(out_dir, "compare-back-side.png")
out.save(p)
print("saved", p, out.size)
