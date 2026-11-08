import os
from PIL import Image

SRC = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\renders\r0006"
OUT = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\v7c"
os.makedirs(OUT, exist_ok=True)

def crop(view, box, name, scale=2, bg=(20, 20, 26, 255)):
    im = Image.open(os.path.join(SRC, f"{view}_2400.png")).convert("RGBA")
    c = im.crop(box)
    c = c.resize((int(c.width * scale), int(c.height * scale)), Image.NEAREST)
    b = Image.new("RGBA", c.size, bg)
    b.alpha_composite(c)
    b.convert("RGB").save(os.path.join(OUT, name))
    print("wrote", name, c.size)

def fit(view, box, name, maxw=1400):
    im = Image.open(os.path.join(SRC, f"{view}_2400.png")).convert("RGBA")
    c = im.crop(box)
    s = maxw / c.width
    c = c.resize((int(c.width * s), int(c.height * s)), Image.LANCZOS)
    b = Image.new("RGBA", c.size, (20, 20, 26, 255))
    b.alpha_composite(c)
    b.convert("RGB").save(os.path.join(OUT, name))
    print("wrote", name, c.size)

# skirt band in 2400: rows ~1380..1700, x 800..1600
fit("front", (800, 1360, 1600, 1700), "closeup-skirt-front.png")
fit("left", (800, 1360, 1600, 1700), "closeup-skirt-left.png")
fit("back", (800, 1360, 1600, 1700), "closeup-skirt-back.png")
fit("iso_fr", (800, 1360, 1600, 1700), "closeup-skirt-iso_fr.png")
crop("front", (1000, 1000, 1400, 1200), "closeup-waist-front-2x.png", 2.6)
crop("front", (1020, 1440, 1380, 1640), "closeup-front-notch-2x.png", 2.6)
