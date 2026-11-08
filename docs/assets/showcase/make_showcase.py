from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path
repo = str(Path(__file__).resolve().parents[3])
out = os.path.join(repo, "docs", "assets", "showcase")
os.makedirs(out, exist_ok=True)
def font(size, bold=False):
    p = r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"
    return ImageFont.truetype(p, size)

# 1) final 4 views
r = os.path.join(repo, "models", "togawa-sakiko", "artifacts", "renders", "r0023")
views = [("front", "front_768.png"), ("back", "back_768.png"), ("left", "left_768.png"), ("iso_fr", "iso_fr_768.png")]
cell = 430
sheet = Image.new("RGB", (cell*4, cell+40), (22,22,26))
d = ImageDraw.Draw(sheet)
f = font(22, True)
for i,(lab, fn) in enumerate(views):
    im = Image.open(os.path.join(r, fn)).convert("RGB").resize((cell, cell), Image.LANCZOS)
    sheet.paste(im, (i*cell, 40))
    d.rectangle([i*cell, 0, i*cell+cell-1, 39], fill=(12,12,16))
    d.text((12, 8), lab, fill=(255,220,90), font=f)
sheet.save(os.path.join(out, "sakiko-final-4views.png"))
print("4views ok", os.path.getsize(os.path.join(out, "sakiko-final-4views.png")))

# 2) before/after: r0021 (217) vs r0023 (401)
rows = [("BEFORE 217 cubes (first T1 acceptance)", os.path.join(repo,"models","togawa-sakiko","artifacts","renders","r0021")),
        ("AFTER T2 + v2 refinement 401 cubes", r)]
views2 = ["front_768.png","back_768.png","left_768.png","iso_fr_768.png"]
c2 = 420; lh = 36
ba = Image.new("RGB", (c2*4, (c2+lh)*2), (22,22,26))
db = ImageDraw.Draw(ba); f2 = font(20, True)
for ri,(lab, folder) in enumerate(rows):
    y0 = ri*(c2+lh)
    db.rectangle([0,y0,c2*4,y0+lh], fill=(12,12,16))
    db.text((10,y0+7), lab, fill=(255,220,90), font=f2)
    for ci,fn in enumerate(views2):
        p = os.path.join(folder, fn)
        if not os.path.exists(p): continue
        im = Image.open(p).convert("RGB").resize((c2,c2), Image.LANCZOS)
        ba.paste(im, (ci*c2, y0+lh))
        db.rectangle([ci*c2,y0+lh,ci*c2+c2-1,y0+lh+c2-1], outline=(40,40,46))
ba.save(os.path.join(out, "sakiko-before-after.png"))
print("ba ok", os.path.getsize(os.path.join(out,"sakiko-before-after.png")))

# 3) T2 29 layers sheet (resize existing)
src = os.path.join(repo,"models","togawa-sakiko","artifacts","t2-preview","layer-sheet.png")
if os.path.exists(src):
    im = Image.open(src).convert("RGB")
    im.thumbnail((1600,1600), Image.LANCZOS)
    im.save(os.path.join(out,"t2-29-layers.png"))
    print("layers ok", os.path.getsize(os.path.join(out,"t2-29-layers.png")))

# 4) head/horn detail from final front + iso crops
front = Image.open(os.path.join(r,"front_768.png")).convert("RGB")
iso = Image.open(os.path.join(r,"iso_fr_768.png")).convert("RGB")
# crop head area (top ~360px) from front and iso
fh = front.crop((190, 20, 580, 360)).resize((780, 680), Image.LANCZOS)
ih = iso.crop((250, 20, 520, 300)).resize((540, 560), Image.LANCZOS)
det = Image.new("RGB", (780+540+20, 680+40), (22,22,26))
dd = ImageDraw.Draw(det)
det.paste(fh,(0,40)); det.paste(ih,(800,40))
dd.rectangle([0,0,780+540+20,39], fill=(12,12,16))
dd.text((12,8), "head / horns / eyes — front + iso (final v2)", fill=(255,220,90), font=f2)
det.save(os.path.join(out,"sakiko-detail-head.png"))
print("detail ok", os.path.getsize(os.path.join(out,"sakiko-detail-head.png")))
