from PIL import Image
from collections import Counter
root = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\textures"
for name in ("default.png", "blue.png"):
    im = Image.open(root + "\\" + name).convert("RGBA")
    W, H = im.size
    px = list(im.getdata())
    c = Counter(px)
    nb = [(i % W, i // W, p) for i, p in enumerate(px) if p[3] > 0]
    print(name, "unique:", len(c), "opaque:", len(nb))
    print("  top:", c.most_common(10))
    if nb:
        xs = [p[0] for p in nb]; ys = [p[1] for p in nb]
        print("  opaque bbox x", min(xs), max(xs), " y", min(ys), max(ys))
    for (x, y) in [(112, 240), (120, 240), (128, 240), (136, 240), (144, 240), (150, 250)]:
        print("   sample", x, y, im.getpixel((x, y)))
