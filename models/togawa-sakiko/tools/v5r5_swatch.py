from PIL import Image
import os

out_dir = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\v5\r5"
os.makedirs(out_dir, exist_ok=True)

B = (30, 39, 71, 128)     # base navy, alpha 0.502
B2 = (35, 46, 82, 128)    # slightly lighter navy
S = (244, 248, 255, 150)  # star sparkle, alpha 0.588
S2 = (201, 223, 255, 150)

px = [[B] * 6 for _ in range(6)]
px[0][2] = S
px[3][1] = S2
px[4][4] = S
px[2][3] = B2
px[5][0] = B2
px[1][5] = B2

im = Image.new("RGBA", (6, 6))
for y in range(6):
    for x in range(6):
        im.putpixel((x, y), px[y][x])
p = os.path.join(out_dir, "star_swatch.png")
im.save(p)
print("saved", p)
print("alpha max", max(p[3] for row in px for p in row) / 255)
