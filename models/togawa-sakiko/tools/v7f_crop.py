import os
from PIL import Image
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
src = Image.open(os.path.join(BASE, "artifacts", "v7e", "isolate-hair-top.png")).convert("RGBA")
out = os.path.join(BASE, "artifacts", "v7f")
os.makedirs(out, exist_ok=True)
W, H = src.size
print(src.size)
# crown center region
box = (int(W*0.30), int(H*0.24), int(W*0.72), int(H*0.62))
c = src.crop(box).resize((1200, int(1200*(box[3]-box[1])/(box[2]-box[0]))), Image.NEAREST)
bg = Image.new("RGBA", c.size, (28, 28, 34, 255)); bg.alpha_composite(c); bg.convert("RGB").save(os.path.join(out, "crop-crown-before.png"))
# corner tab region (top-right diagonal)
box2 = (int(W*0.60), int(H*0.24), int(W*0.80), int(H*0.44))
c2 = src.crop(box2).resize((900, 900), Image.NEAREST)
bg2 = Image.new("RGBA", c2.size, (28, 28, 34, 255)); bg2.alpha_composite(c2); bg2.convert("RGB").save(os.path.join(out, "crop-corner-before.png"))
print("ok")
