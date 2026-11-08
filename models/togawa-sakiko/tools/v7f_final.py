import os, shutil
from PIL import Image
import numpy as np
from collections import deque
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
OUT = os.path.join(BASE, "artifacts", "v7f")
# final isolate top = rev25 render
shutil.copy2(os.path.join(BASE, "artifacts", "renders", "r0025", "top_2400.png"),
             os.path.join(OUT, "isolate-hair-top.png"))
# head close-up from the 2400 front render (same visible geometry as rev25)
fr = Image.open(os.path.join(OUT, "final-front-2400.png")).convert("RGBA")
crop = fr.crop((640, 120, 1760, 940)).resize((1568, 1148), Image.NEAREST)
bg = Image.new("RGBA", crop.size, (26, 26, 32, 255)); bg.alpha_composite(crop)
bg.convert("RGB").save(os.path.join(OUT, "head-closeup-front.png"))
# top compare v7e vs v7f final
def load(p, box, size, bgc=(26, 26, 32, 255)):
    im = Image.open(p).convert("RGBA"); W, H = im.size
    b = (int(W*box[0]), int(H*box[1]), int(W*box[2]), int(H*box[3]))
    c = im.crop(b).resize(size, Image.NEAREST)
    b2 = Image.new("RGBA", c.size, bgc); b2.alpha_composite(c); return b2.convert("RGB")
a = load(os.path.join(BASE, "artifacts", "v7e", "isolate-hair-top.png"), (0.10, 0.16, 0.90, 0.88), (800, 640))
b = load(os.path.join(OUT, "isolate-hair-top.png"), (0.10, 0.16, 0.90, 0.88), (800, 640))
c = Image.new("RGB", (800*2+16, 640), (18, 18, 22)); c.paste(a, (0, 0)); c.paste(b, (816, 0))
c.save(os.path.join(OUT, "cmp-top-v7e_vs_v7f.png"))
# hole detection on final top
im = Image.open(os.path.join(OUT, "isolate-hair-top.png")).convert("RGBA")
arr = np.array(im); al = arr[:, :, 3]
a2 = al[::3, ::3]; m = a2 > 8
H, W = m.shape
seen = np.zeros((H, W), bool); dq = deque()
for x in range(W):
    for y in (0, H-1):
        if not m[y, x] and not seen[y, x]: seen[y, x] = True; dq.append((y, x))
for y in range(H):
    for x in (0, W-1):
        if not m[y, x] and not seen[y, x]: seen[y, x] = True; dq.append((y, x))
while dq:
    y, x = dq.popleft()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ny, nx = y+dy, x+dx
        if 0 <= ny < H and 0 <= nx < W and not m[ny, nx] and not seen[ny, nx]:
            seen[ny, nx] = True; dq.append((ny, nx))
enc = (~m) & (~seen)
print("final isolate-top enclosed transparent px (grid 3):", int(enc.sum()), "-> full-res approx", int(enc.sum())*9)
# mark them
mk = enc.repeat(3, 0).repeat(3, 1)[:arr.shape[0], :arr.shape[1]]
arr2 = arr.copy(); arr2[mk] = [255, 30, 30, 255]
img = Image.fromarray(arr2); b3 = Image.new("RGBA", img.size, (30, 30, 36, 255)); b3.alpha_composite(img)
b3.convert("RGB").save(os.path.join(OUT, "holes-marked-top-final.png"))
print("done")
