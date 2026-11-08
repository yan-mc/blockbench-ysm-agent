from PIL import Image

root = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\renders\r0008"
back = Image.open(root + r"\back_800.png").convert("RGB")
right = Image.open(root + r"\right_800.png").convert("RGB")
print(back.size, right.size)

crops = [
    ("back-skirt-zoom", back.crop((240, 300, 560, 620)), 2),
    ("back-hair-zoom", back.crop((160, 40, 640, 360)), 1),
    ("side-hair-zoom", right.crop((180, 40, 470, 480)), 1),
]
W = sum(c.width * s for _, c, s in crops) + 12 * (len(crops) - 1)
H = max(c.height * s for _, c, s in crops)
out = Image.new("RGB", (W, H), (250, 250, 250))
x = 0
for name, c, s in crops:
    c2 = c.resize((c.width * s, c.height * s), Image.LANCZOS)
    out.paste(c2, (x, 0))
    x += c2.width + 12
out.save(r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\v5\r5\_zoom1.png")
print("saved", out.size)
