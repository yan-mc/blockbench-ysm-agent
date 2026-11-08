import os
import numpy as np
from PIL import Image
from collections import deque
BASE = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
def mark(path, out, scale=2):
    im = Image.open(path).convert("RGBA")
    arr = np.array(im)
    a = arr[:, :, 3]
    small = a[::scale, ::scale]
    m = small > 8
    H, W = m.shape
    seen = np.zeros((H, W), bool); dq = deque()
    for x in range(W):
        for y in (0, H-1):
            if not m[y, x] and not seen[y, x]: seen[y, x] = True; dq.append((y, x))
    for y in range(H):
        for x in (0, W-1):
            if not m[y, x] and not seen[y, x]: seen[y, x] = True; dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y+dy, x+dx
            if 0 <= ny < H and 0 <= nx < W and not m[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True; dq.append((ny, nx))
    enc = (~m) & (~seen)
    if scale > 1:
        enc = np.repeat(np.repeat(enc, scale, 0), scale, 1)
    enc = enc[:arr.shape[0], :arr.shape[1]]
    arr[enc] = [255, 30, 30, 255]
    img = Image.fromarray(arr)
    bg = Image.new("RGBA", img.size, (30, 30, 36, 255)); bg.alpha_composite(img)
    bg.convert("RGB").save(out)
    print("saved", out, "holes px", int(enc.sum()))
mark(os.path.join(BASE, "artifacts", "renders", "r0022", "top_2400.png"),
     os.path.join(BASE, "artifacts", "v7f", "holes-marked-top.png"))
mark(os.path.join(BASE, "artifacts", "v7e", "isolate-hair-top.png"),
     os.path.join(BASE, "artifacts", "v7f", "holes-marked-v7e-top.png"))
