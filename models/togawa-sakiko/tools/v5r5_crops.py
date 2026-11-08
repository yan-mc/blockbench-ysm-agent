from PIL import Image

root = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\refstudy"
back = Image.open(root + r"\t3-panel5-back.png").convert("RGB")
side = Image.open(root + r"\t3-panel5-side.png").convert("RGB")
front = Image.open(root + r"\t3-panel5-front.png").convert("RGB")

crops = [
    ("back-skirt", back.crop((40, 400, 520, 780))),
    ("side-skirt", side.crop((0, 400, 395, 780))),
    ("back-head", back.crop((60, 20, 500, 400))),
    ("front-skirt", front.crop((60, 430, 500, 780))),
]
scale = 2
w = sum(c.width * scale for _, c in crops) + 10 * (len(crops) - 1)
h = max(c.height * scale for _, c in crops) + 24
out = Image.new("RGB", (w, h), (255, 255, 255))
x = 0
for name, c in crops:
    c2 = c.resize((c.width * scale, c.height * scale), Image.LANCZOS)
    out.paste(c2, (x, 24))
    x += c2.width + 10
out.save(root + r"\_check_crops.png")
print("saved", out.size, [n for n, _ in crops])
