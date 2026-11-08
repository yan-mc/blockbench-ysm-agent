from PIL import Image
im = Image.open(r'F:\Deepseek_harness\blockbench\models\togawa-sakiko\pack\textures\default.png').convert('RGBA')
pts = [(206, 14), (238, 14), (85, 229), (69, 229), (53, 229), (117, 229), (133, 229),
       (118, 294), (165, 229), (300, 470), (316, 486), (5, 229), (21, 229), (37, 229),
       (214, 294), (134, 294), (150, 294), (54, 246), (38, 246), (70, 246), (86, 246)]
for (x, y) in pts:
    c = im.getpixel((x + 1, y + 1))
    print((x, y), "#%02x%02x%02x" % c[:3], "a", c[3])
