from PIL import Image
im = Image.open(r"F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\textures\default.png").convert("RGBA")
px = im.load()
def region_stats(u,v,w,h):
    cols=[]
    for y in range(v, v+int(round(h))+1):
        for x in range(u, u+int(round(w))+1):
            cols.append(px[x,y])
    mn=tuple(min(c[i] for c in cols) for i in range(3))
    mx=tuple(max(c[i] for c in cols) for i in range(3))
    avg=tuple(sum(c[i] for c in cols)//len(cols) for i in range(3))
    return avg, mn, mx
for (u,v) in [(226,18),(200,18),(258,18),(100,230),(116,230),(132,230),(150,230),(164,230)]:
    for (w,h) in [(3.2,9.0),(2.0,1.5),(3.6,1.0)]:
        print((u,v),(w,h), region_stats(u,v,w,h))
