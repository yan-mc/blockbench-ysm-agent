import os
from PIL import Image

SRC = r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\renders\r0045'
OUT = r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\artifacts\v7a'
os.makedirs(OUT, exist_ok=True)

crops = {
    'front': (880, 1060, 1520, 1720),
    'left':  (880, 1060, 1520, 1720),
    'back':  (880, 1060, 1520, 1720),
}
for v, box in crops.items():
    im = Image.open(os.path.join(SRC, f'{v}_2400.png')).convert('RGBA')
    c = im.crop(box)
    c = c.resize((c.width * 2, c.height * 2), Image.NEAREST)
    c.save(os.path.join(OUT, f'inspect-skirt-{v}.png'))
    print(v, im.size, c.size)
