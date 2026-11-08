import os
from PIL import Image
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
out = os.path.join(BASE, "artifacts", "v7f")
def crop(path, box, size, bg=(26, 26, 32, 255)):
    im = Image.open(path).convert("RGBA"); W, H = im.size
    b = (int(W*box[0]), int(H*box[1]), int(W*box[2]), int(H*box[3]))
    c = im.crop(b).resize(size, Image.NEAREST)
    bgim = Image.new("RGBA", c.size, bg); bgim.alpha_composite(c)
    return bgim.convert("RGB")
a = crop(os.path.join(BASE, "artifacts", "v7e", "isolate-hair-top.png"), (0.33, 0.30, 0.67, 0.64), (820, 820))
b = crop(os.path.join(BASE, "artifacts", "renders", "r0022", "top_2400.png"), (0.33, 0.30, 0.67, 0.64), (820, 820))
c = Image.new("RGB", (820*2+16, 820), (18, 18, 22)); c.paste(a, (0, 0)); c.paste(b, (836, 0))
c.save(os.path.join(out, "cmp-top-crown-v7e_vs_v7f.png"))
# full top view new vs old
a2 = crop(os.path.join(BASE, "artifacts", "v7e", "isolate-hair-top.png"), (0.12, 0.18, 0.88, 0.86), (760, 700))
b2 = crop(os.path.join(BASE, "artifacts", "renders", "r0022", "top_2400.png"), (0.12, 0.18, 0.88, 0.86), (760, 700))
c2 = Image.new("RGB", (760*2+16, 700), (18, 18, 22)); c2.paste(a2, (0, 0)); c2.paste(b2, (776, 0))
c2.save(os.path.join(out, "cmp-top-full-v7e_vs_v7f.png"))
print("ok")
