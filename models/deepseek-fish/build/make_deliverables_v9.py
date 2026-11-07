"""Assemble the v9 deliverables: copy 8 view renders + build head closeup +
before/after eye comparison."""
from PIL import Image
import numpy as np, os, shutil

WS = r"F:\Deepseek_harness\blockbench\models\deepseek-fish"
SRC = os.path.join(WS, "artifacts", "renders", "r0009")
DST = os.path.join(WS, "deliverables", "sakiko-melodia-v9")
os.makedirs(DST, exist_ok=True)

pairs = [
    ("front_1600.png", "01_front.png"),
    ("back_1600.png", "02_back.png"),
    ("left_1600.png", "03_left.png"),
    ("right_1600.png", "04_right.png"),
    ("iso_fr_1600.png", "05_iso_front_right.png"),
    ("iso_fl_1600.png", "06_iso_front_left.png"),
    ("iso_br_1600.png", "07_iso_back_right.png"),
    ("iso_bl_1600.png", "08_iso_back_left.png"),
]
for s, d in pairs:
    shutil.copy(os.path.join(SRC, s), os.path.join(DST, d))
    print("copied", d)

# --- head closeup from the front render
im = Image.open(os.path.join(DST, "01_front.png")).convert("RGBA")
a = np.array(im)[:, :, 3]
ys, xs = np.nonzero(a > 8)
y0, y1 = ys.min(), ys.max()
x0, x1 = xs.min(), xs.max()
h = y1 - y0
cy1 = y0 + int(h * 0.312)
cx0 = x0 + int((x1 - x0) * 0.30)
cx1 = x0 + int((x1 - x0) * 0.70)
crop = im.crop((cx0, max(0, y0 - 8), cx1, cy1))
scale = max(1, int(900 / crop.width))
crop = crop.resize((crop.width * scale, crop.height * scale), Image.NEAREST)
crop.save(os.path.join(DST, "09_head_closeup.png"))
print("head closeup", crop.size)

# --- before / after comparison (v8 closeup vs v9 crop)
v8 = Image.open(os.path.join(WS, "deliverables", "sakiko-melodia-v8", "09_head_closeup.png")).convert("RGBA")
v9 = crop
H = 760
v8r = v8.resize((int(v8.width * H / v8.height), H), Image.NEAREST)
v9r = v9.resize((int(v9.width * H / v9.height), H), Image.NEAREST)
pad = 16
out = Image.new("RGBA", (v8r.width + v9r.width + pad * 3, H + pad * 2), (34, 34, 40, 255))
out.paste(v8r, (pad, pad), v8r)
out.paste(v9r, (pad * 2 + v8r.width, pad), v9r)
out.save(os.path.join(DST, "10_eyes_before_after.png"))
print("comparison", out.size)

