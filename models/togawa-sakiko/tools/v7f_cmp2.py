import os
from PIL import Image
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
out = os.path.join(BASE, "artifacts", "v7f")
def crop(path, box, size, bg=(26, 26, 32, 255)):
    im = Image.open(path).convert("RGBA")
    W, H = im.size
    b = (int(W*box[0]), int(H*box[1]), int(W*box[2]), int(H*box[3]))
    c = im.crop(b)
    c = c.resize(size, Image.NEAREST)
    bgim = Image.new("RGBA", c.size, bg); bgim.alpha_composite(c)
    return bgim.convert("RGB")

# back: upper hair region
b1 = crop(os.path.join(BASE, "artifacts", "v7e", "final-back-2400.png"), (0.28, 0.05, 0.72, 0.60), (760, 860))
b2 = crop(os.path.join(BASE, "artifacts", "renders", "r0021", "back_2400.png"), (0.28, 0.05, 0.72, 0.60), (760, 860))
cmp1 = Image.new("RGB", (760*2+16, 860), (18, 18, 22))
cmp1.paste(b1, (0, 0)); cmp1.paste(b2, (776, 0))
cmp1.save(os.path.join(out, "cmp-back-v7e_vs_v7f.png"))
# left side
l1 = crop(os.path.join(BASE, "artifacts", "v7e", "final-left-2400.png"), (0.30, 0.03, 0.72, 0.75), (700, 900))
l2 = crop(os.path.join(BASE, "artifacts", "renders", "r0021", "left_2400.png"), (0.30, 0.03, 0.72, 0.75), (700, 900))
cmp2 = Image.new("RGB", (700*2+16, 900), (18, 18, 22))
cmp2.paste(l1, (0, 0)); cmp2.paste(l2, (716, 0))
cmp2.save(os.path.join(out, "cmp-left-v7e_vs_v7f.png"))
# crown from front
c1 = crop(os.path.join(BASE, "artifacts", "v7e", "final-front-2400.png"), (0.33, 0.04, 0.67, 0.30), (900, 700))
c2 = crop(os.path.join(BASE, "artifacts", "renders", "r0021", "front_2400.png"), (0.33, 0.04, 0.67, 0.30), (900, 700))
cmp3 = Image.new("RGB", (900*2+16, 700), (18, 18, 22))
cmp3.paste(c1, (0, 0)); cmp3.paste(c2, (916, 0))
cmp3.save(os.path.join(out, "cmp-crown-front-v7e_vs_v7f.png"))
print("ok")

