import os
import shutil
from PIL import Image

root = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
ren = os.path.join(root, "artifacts", "renders", "r0017")
ref = os.path.join(root, "artifacts", "refstudy")
out = os.path.join(root, "artifacts", "v5", "r5")
os.makedirs(out, exist_ok=True)

files = {
    "front": "v5-r5-front-2400.png",
    "back": "v5-r5-back-2400.png",
    "left": "v5-r5-left-2400.png",
    "iso_fr": "v5-r5-iso_fr-2400.png",
}
for k, v in files.items():
    src = os.path.join(ren, k + "_2400.png")
    dst = os.path.join(out, v)
    shutil.copyfile(src, dst)
    print("copied", v, os.path.getsize(dst))

# head closeups
for k, v in (("front", "v5-r5-head-front-1600.png"), ("back", "v5-r5-head-back-1600.png")):
    src = os.path.join(ren, k + "_1600.png")
    shutil.copyfile(src, os.path.join(out, v))
    print("copied", v)

# back closeup crop from 2400 back render
back = Image.open(os.path.join(ren, "back_2400.png")).convert("RGB")
W, H = back.size
crop = back.crop((int(W * 0.28), int(H * 0.05), int(W * 0.72), int(H * 0.72)))
crop.save(os.path.join(out, "v5-r5-back-closeup.png"))
print("back closeup", crop.size)

# final T3-vs-v5 comparison sheet: front / side / back
panels = [
    ("front", "t3-panel5-front.png", os.path.join(ren, "front_2400.png")),
    ("side", "t3-panel5-side.png", os.path.join(ren, "left_2400.png")),
    ("back", "t3-panel5-back.png", os.path.join(ren, "back_2400.png")),
]
CH = 1000
cols = []
for name, rp, vp in panels:
    ia = Image.open(os.path.join(ref, rp)).convert("RGB")
    ib = Image.open(vp).convert("RGB")
    for im, tag in ((ia, "T3"), (ib, "v5r5")):
        s = CH / im.height
        im2 = im.resize((max(1, int(im.width * s)), CH), Image.LANCZOS)
        cols.append(im2)
W2 = sum(c.width for c in cols) + 10 * (len(cols) - 1)
sheet = Image.new("RGB", (W2, CH), (248, 248, 248))
x = 0
for c in cols:
    sheet.paste(c, (x, 0))
    x += c.width + 10
p = os.path.join(out, "v5-r5-vs-T3-correct.png")
sheet.save(p)
print("sheet", sheet.size, p)

