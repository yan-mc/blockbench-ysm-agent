from PIL import Image
base = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\textures\default.png"
im = Image.open(base).convert("RGBA")
W,H = im.size
px = im.load()
def ch(r,g,b,a):
    if a < 100: return "."
    mx,mn = max(r,g,b), min(r,g,b)
    if mx < 60: return "K"      # black
    if mx < 110 and mx-mn < 30: return "k"  # dark gray
    if b > r+40 and b > 100: return "B"     # blue
    if b > r+15 and mx > 150: return "b"    # pale blue
    if mn > 190: return "W"     # white
    if r > 150 and g > 120 and b > 100 and r >= g >= b: return "S" # skin
    if r > 140 and b > 140: return "P"      # purple/pink
    if r > 120 and g > 90 and b < 90: return "Y" # gold
    return "?"
step = 8
print("    " + "".join(str((x//step)%10) for x in range(0,W,step)))
for y in range(0,H,step):
    row = []
    for x in range(0,W,step):
        # majority of 8x8
        from collections import Counter
        c = Counter()
        for yy in range(y,min(y+step,H),2):
            for xx in range(x,min(x+step,W),2):
                c[ch(*px[xx,yy])] += 1
        row.append(c.most_common(1)[0][0])
    print(f"{y:4d}" + "".join(row))
