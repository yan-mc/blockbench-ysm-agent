import os
import shutil
from PIL import Image

root = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
ren = os.path.join(root, "artifacts", "renders", "r0018")
ren_head = os.path.join(root, "artifacts", "renders", "r0017")
ref = os.path.join(root, "artifacts", "refstudy")
out = os.path.join(root, "artifacts", "v5", "r5")
os.makedirs(out, exist_ok=True)

for k, v in {
    "front": "v5-r5-front-2400.png",
    "back": "v5-r5-back-2400.png",
    "left": "v5-r5-left-2400.png",
    "iso_fr": "v5-r5-iso_fr-2400.png",
}.items():
    shutil.copyfile(os.path.join(ren, k + "_2400.png"), os.path.join(out, v))
    print("copy", v)

for k, v in (("front", "v5-r5-head-front-1600.png"), ("back", "v5-r5-head-back-1600.png")):
    shutil.copyfile(os.path.join(ren_head, k + "_1600.png"), os.path.join(out, v))
    print("copy", v)

back = Image.open(os.path.join(ren, "back_2400.png")).convert("RGB")
W, H = back.size
back.crop((int(W * 0.30), int(H * 0.06), int(W * 0.70), int(H * 0.66))).save(
    os.path.join(out, "v5-r5-back-closeup.png")
)

panels = [
    ("t3-panel5-front.png", "front_2400.png"),
    ("t3-panel5-side.png", "left_2400.png"),
    ("t3-panel5-back.png", "back_2400.png"),
]
CH = 1000
cols = []
for rp, vp in panels:
    for p, tag in ((os.path.join(ref, rp), "T3"), (os.path.join(ren, vp), "v5")):
        im = Image.open(p).convert("RGB")
        s = CH / im.height
        cols.append(im.resize((max(1, int(im.width * s)), CH), Image.LANCZOS))
W2 = sum(c.width for c in cols) + 10 * (len(cols) - 1)
sheet = Image.new("RGB", (W2, CH), (248, 248, 248))
x = 0
for c in cols:
    sheet.paste(c, (x, 0))
    x += c.width + 10
sheet.save(os.path.join(out, "v5-r5-vs-T3-correct.png"))
print("sheet", sheet.size)
print("files:", sorted(os.listdir(out)))
