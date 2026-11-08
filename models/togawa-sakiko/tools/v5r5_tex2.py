from PIL import Image
from collections import Counter
root = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\textures"
im = Image.open(root + "\\default.png").convert("RGBA")

print("== default.png region x100-180 y225-275 (color counts) ==")
reg = im.crop((100, 225, 180, 275))
c = Counter(reg.getdata())
print(c.most_common(20))

# print coarse map: for each 2x2 block pick first pixel
chars = {}
def ch(p):
    if p[3] == 0:
        return "."
    key = p
    if key not in chars:
        chars[key] = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"[len(chars) % 62]
    return chars[key]
print("== map (x from 100, y from 225), 2px step ==")
hdr = "    " + "".join(str((100 + i * 2) // 10 % 10) for i in range(40))
print(hdr)
for y in range(225, 275, 2):
    line = "".join(ch(im.getpixel((100 + i * 2, y))) for i in range(40))
    print(f"{y:3d} " + line)
print("legend:", {v: k for k, v in chars.items()})

# where is unused (fully transparent) region large enough
W = H = 512
import numpy as np
a = np.array(im)
alpha = a[:, :, 3]
rows = [(y, int((alpha[y] == 0).sum())) for y in range(256, 512)]
print("transparent count per row sample:", rows[::16])
