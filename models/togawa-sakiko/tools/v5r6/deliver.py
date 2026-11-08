from PIL import Image
import os
root = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
out = root + r"\artifacts\v5\r6"

back = Image.open(out + r"\v5-r6-back-2400.png").convert("RGBA")
print("back", back.size)
# figure bbox from renderer: x 0.335-0.6646, y 0.1046-0.9346 of 2400
x0, x1 = int(2400 * 0.335), int(2400 * 0.6646)
y0, y1 = int(2400 * 0.1046), int(2400 * 0.9346)
# model y = 43.17 at y0, 0 at y1
def py(y):
    return int(y1 - (y / 43.17) * (y1 - y0))

top, bot = py(25.5), py(11.5)          # hair->skirt->upper legs
cx = (x0 + x1) // 2
half = 620
crop = back.crop((cx - half, top, cx + half, top + 2 * half))
crop.save(out + r"\v5-r6-back-closeup.png")
print("closeup", crop.size, top)

# comparison sheet T3 back vs r6 back (same figure height)
t3 = Image.open(root + r"\artifacts\refstudy\t3-panel5-back.png").convert("RGB").crop((0, 20, 540, 1090))
H = 900
t3r = t3.resize((int(t3.width * H / t3.height), H))
ours = back.crop((x0 - 20, y0 - 20, x1 + 20, y1 + 20)).convert("RGB")
ourr = ours.resize((int(ours.width * H / ours.height), H))
canvas = Image.new("RGB", (t3r.width + ourr.width + 30, H + 16), (40, 40, 46))
canvas.paste(t3r, (0, 8))
canvas.paste(ourr, (t3r.width + 30, 8))
canvas.save(out + r"\cmp_back_t3_vs_r6.png")
print("cmp", canvas.size)
