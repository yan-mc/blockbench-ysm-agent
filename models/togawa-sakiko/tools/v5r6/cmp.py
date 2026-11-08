from PIL import Image
import os
root = r"F:\Deepseek_harness\blockbench\models\togawa-sakiko"
out = root + r"\artifacts\v5\r6"

t3 = Image.open(root + r"\artifacts\refstudy\t3-panel5-back.png").convert("RGB").crop((0, 20, 540, 1090))
# our back cell
im = Image.open(r"C:\Users\28988\.dsh\attachments\v1\objects\29\2983bed180e757909c8fcfedfd59155a3971dab40892bf90d50d97cdff76956d").convert("RGB").crop((0, 0, 700, 700))
# crop figure bbox of our render: find non-bg
import numpy as np
a = np.array(im).astype(int)
bg = (abs(a[:, :, 0] - 58) < 6) & (abs(a[:, :, 1] - 58) < 6) & (abs(a[:, :, 2] - 66) < 6)
fg = ~bg
cols = np.where(fg.any(axis=0))[0]; rows = np.where(fg.any(axis=1))[0]
our = im.crop((cols.min() - 10, rows.min() - 10, cols.max() + 10, rows.max() + 10))

H = 760
t3r = t3.resize((int(t3.width * H / t3.height), H))
ourr = our.resize((int(our.width * H / our.height), H))
canvas = Image.new("RGB", (t3r.width + ourr.width + 30, H + 20), (40, 40, 46))
canvas.paste(t3r, (0, 10))
canvas.paste(ourr, (t3r.width + 30, 10))
canvas.save(out + r"\cmp_back_t3_vs_r6.png")
print(canvas.size)
