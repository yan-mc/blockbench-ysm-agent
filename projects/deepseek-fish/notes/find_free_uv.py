from PIL import Image
import sys

p = sys.argv[1] if len(sys.argv) > 1 else r'F:\Deepseek_harness\blockbench\projects\deepseek-fish\artifacts\textures\default.png'
img = Image.open(p).convert('RGBA')
w, h = img.size
px = img.load()

def free_block(x, y, bw, bh):
    for yy in range(y, y + bh):
        for xx in range(x, x + bw):
            if px[xx, yy][3] != 0:
                return False
    return True

# 找互不重叠的 8x8 全透明块，优先靠下/靠边
used = []
candidates = []
for bh, bw in [(8, 8), (4, 4), (2, 2)]:
    for y in range(0, h - bh + 1, 1):
        for x in range(0, w - bw + 1, 1):
            if not free_block(x, y, bw, bh):
                continue
            overlap = any(not (x + bw <= ux or ux + uw <= x or y + bh <= uy or uy + uh <= y) for ux, uy, uw, uh in used)
            if overlap:
                continue
            candidates.append((x, y, bw, bh))
            used.append((x, y, bw, bh))
            if len(used) >= 12:
                break
        if len(used) >= 12:
            break
    if len(used) >= 12:
        break

print('free blocks:', used)
# 输出 128 网格的 alpha 可视化（16x16 块）
for yy in range(0, h, 16):
    row = ''
    for xx in range(0, w, 16):
        if free_block(xx, yy, 16, 16):
            row += 'F'
        elif free_block(xx, yy, 8, 8):
            row += 'f'
        else:
            row += '.'
    print(yy, row)
