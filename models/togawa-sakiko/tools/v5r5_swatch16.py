from PIL import Image
import os

out_dir = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\v5\r5"
B = (30, 39, 71, 128)
B2 = (35, 46, 82, 128)
B3 = (26, 33, 61, 128)
S = (244, 248, 255, 150)
S2 = (201, 223, 255, 150)

im = Image.new("RGBA", (16, 16), B)
px = im.load()
# subtle vertical banding (fabric folds)
for y in range(16):
    for x in range(16):
        if (x // 3) % 2 == 0:
            px[x, y] = B2
        if (x // 5) % 3 == 0:
            px[x, y] = B3
# star sparkles (1px)
for (x, y) in [(2, 3), (7, 1), (12, 5), (4, 9), (10, 11), (14, 14), (1, 13)]:
    px[x, y] = S
for (x, y) in [(9, 7), (5, 14), (13, 2)]:
    px[x, y] = S2
p = os.path.join(out_dir, "star_swatch16.png")
im.save(p)
print("saved", p, im.size, "alpha", max(S[3], S2[3], 128) / 255)
