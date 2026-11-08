import os
from PIL import Image, ImageDraw

B = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts"
OUT = os.path.join(B, "v7c")

# --- waist crop (skirt top ring at ~row 1102 in 2400 render)
im = Image.open(os.path.join(B, "renders", "r0006", "front_2400.png")).convert("RGBA")
c = im.crop((980, 1020, 1420, 1220))
c = c.resize((c.width * 2, c.height * 2), Image.NEAREST)
bg = Image.new("RGBA", c.size, (20, 20, 26, 255))
bg.alpha_composite(c)
bg.convert("RGB").save(os.path.join(OUT, "closeup-waist-front-2x.png"))
print("waist crop", c.size)

# --- comparison montage: T3 top row (front/side/back), v7c bottom row
def load(p, h):
    im = Image.open(p).convert("RGB")
    s = h / im.height
    return im.resize((int(im.width * s), h), Image.LANCZOS)

H = 900
panels_top = [load(os.path.join(B, "refstudy", f"t3-panel5-{k}.png"), H) for k in ("front", "side", "back")]
panels_bot = [load(os.path.join(OUT, f"final-{k}-2400.png"), H) for k in ("front", "left", "back")]
labels = [("T3", "REF"), ("T3", "REF"), ("T3", "REF")]
w = max(sum(p.width for p in panels_top), sum(p.width for p in panels_bot)) + 40
canvas = Image.new("RGB", (w, 2 * H + 120), (240, 240, 242))
dr = ImageDraw.Draw(canvas)
for row, panels in enumerate((panels_top, panels_bot)):
    x = 20
    y = 20 + row * (H + 60)
    for i, p in enumerate(panels):
        canvas.paste(p, (x, y))
        dr.text((x + 8, y + 8), ("T3 " if row == 0 else "v7c ") + ["FRONT", "SIDE", "BACK"][i],
                fill=(30, 30, 40))
        x += p.width + 8
canvas.save(os.path.join(OUT, "compare-t3-vs-v7c.png"))
print("montage", canvas.size)

