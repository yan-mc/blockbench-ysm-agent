from PIL import Image
import sys

p = sys.argv[1] if len(sys.argv) > 1 else r'F:\Deepseek_harness\blockbench\models\deepseek-fish\artifacts\textures\default.png'
img = Image.open(p).convert('RGBA')
w, h = img.size
px = img.load()
free = [[1 if px[x, y][3] == 0 else 0 for x in range(w)] for y in range(h)]
best = (0, 0, 0, 0)
for y1 in range(h):
    for y2 in range(y1, h):
        # find widest run of free in every column across rows
        for x in range(w):
            if not all(free[yy][x] for yy in range(y1, y2 + 1)):
                continue
            x2 = x
            while x2 + 1 < w and all(free[yy][x2 + 1] for yy in range(y1, y2 + 1)):
                x2 += 1
            area = (x2 - x + 1) * (y2 - y1 + 1)
            if area > best[0]:
                best = (area, x, y1, x2, y2)
print('largest free rect area,x1,y1,x2,y2 =', best)

