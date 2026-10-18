"""Generate cover art, social preview and 1920x1080 slides for the intro video.

All imagery comes from the test model (DeepSeek whale-girl / 蓝色大肥鱼).
Run: python media/build_slides.py
"""
import os
import json
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, 'models', 'deepseek-fish', 'screenshots')
OUT = os.path.join(ROOT, 'media', 'frames')
DOCS_ASSETS = os.path.join(ROOT, 'docs', 'assets')
os.makedirs(OUT, exist_ok=True)
os.makedirs(DOCS_ASSETS, exist_ok=True)

W, H = 1920, 1080
BG = (7, 18, 34)
ACCENT = (89, 194, 255)
ACCENT2 = (139, 124, 255)
TEXT = (232, 242, 252)
MUTED = (148, 170, 194)
PANEL = (13, 30, 52)
BORDER = (36, 62, 92)
GREEN = (74, 222, 128)
ORANGE = (251, 191, 36)

def font(size, bold=False):
    path = r'C:\Windows\Fonts\msyhbd.ttc' if bold else r'C:\Windows\Fonts\msyh.ttc'
    return ImageFont.truetype(path, size)

def mono(size):
    return ImageFont.truetype(r'C:\Windows\Fonts\consola.ttf', size)

def textlen(d, s, f):
    b = d.textbbox((0, 0), s, font=f)
    return b[2] - b[0], b[3] - b[1]

def wrap(d, text, f, max_w):
    lines = []
    for raw in text.split('\n'):
        if not raw:
            lines.append('')
            continue
        cur = ''
        for ch in raw:
            if textlen(d, cur + ch, f)[0] <= max_w:
                cur += ch
            else:
                if cur:
                    lines.append(cur)
                cur = ch
        lines.append(cur)
    return lines

def draw_wrapped(d, xy, text, f, fill, max_w, line_h=None):
    x, y = xy
    lines = wrap(d, text, f, max_w)
    lh = line_h or int(f.size * 1.42)
    for i, line in enumerate(lines):
        d.text((x, y + i * lh), line, font=f, fill=fill)

def background():
    img = Image.new('RGB', (W, H), BG)
    # vertical gradient
    top = (10, 26, 48)
    bottom = (4, 10, 20)
    grad = Image.new('RGB', (1, H))
    gd = ImageDraw.Draw(grad)
    for y in range(H):
        t = y / (H - 1)
        gd.point((0, y), fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))
    img = grad.resize((W, H))
    draw = ImageDraw.Draw(img, 'RGBA')
    # glows
    for cx, cy, r, color, alpha in [
        (1560, 170, 520, (44, 137, 220), 54),
        (230, 930, 470, (111, 78, 210), 38),
        (980, 520, 620, (18, 74, 124), 28),
    ]:
        layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (alpha,))
        layer = layer.filter(ImageFilter.GaussianBlur(90))
        img = Image.alpha_composite(img.convert('RGBA'), layer).convert('RGB')
        draw = ImageDraw.Draw(img, 'RGBA')
    # grid
    for x in range(0, W, 64):
        draw.line((x, 0, x, H), fill=(70, 120, 160, 16), width=1)
    for y in range(0, H, 64):
        draw.line((0, y, W, y), fill=(70, 120, 160, 16), width=1)
    # vignette
    vig = Image.new('L', (W, H), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse((-300, -250, W + 300, H + 250), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(180))
    black = Image.new('RGBA', (W, H), (0, 0, 0, 210))
    img = Image.composite(img.convert('RGBA'), black, vig).convert('RGB')
    return img

def header(d, section, tag='DSH × BLOCKBENCH AGENT'):
    d.rounded_rectangle((88, 62, 88 + 470, 62 + 42), radius=21, fill=(18, 42, 70, 210), outline=(55, 104, 148, 160), width=1)
    d.text((112, 72), tag, font=font(20, True), fill=(155, 210, 245))
    d.text((88, 132), section, font=font(18), fill=MUTED)
    d.line((88, 170, W - 88, 170), fill=(50, 86, 120, 170), width=1)

def footer(d, page, total):
    d.text((88, H - 58), 'github.com/yan-mc/blockbench-ysm-agent', font=font(18), fill=(110, 140, 168))
    for i in range(total):
        cx = W - 120 - (total - 1 - i) * 22
        color = ACCENT if i == page else (48, 78, 108)
        d.ellipse((cx - 4, H - 64, cx + 4, H - 56), fill=color)

def panel(d, box, radius=22, fill=PANEL, outline=BORDER, width=2):
    d.rounded_rectangle(box, radius=radius, fill=fill + (235,), outline=outline + (255,), width=width)

def chip(d, x, y, text, color=ACCENT, size=20):
    f = font(size, True)
    tw = textlen(d, text, f)[0]
    d.rounded_rectangle((x, y, x + tw + 34, y + 40), radius=20, fill=(10, 27, 44, 230), outline=color + (200,), width=2)
    d.text((x + 17, y + 6), text, font=f, fill=(240, 248, 255))
    return x + tw + 34

def load_asset(name):
    p = os.path.join(ASSETS, name)
    if not os.path.exists(p):
        return None
    return Image.open(p).convert('RGBA')

def paste_float(base, img, xy, size, shadow=True, border=True):
    if img is None:
        return
    img = img.copy()
    img.thumbnail((size, size), Image.LANCZOS)
    if shadow:
        sh = Image.new('RGBA', (img.width + 80, img.height + 80), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sd.rounded_rectangle((40, 50, 40 + img.width, 50 + img.height), radius=28, fill=(0, 0, 0, 150))
        sh = sh.filter(ImageFilter.GaussianBlur(26))
        base.alpha_composite(sh, (xy[0] - 40, xy[1] - 40))
    if border:
        frame = Image.new('RGBA', (img.width + 16, img.height + 16), (0, 0, 0, 0))
        fd = ImageDraw.Draw(frame)
        fd.rounded_rectangle((0, 0, frame.width - 1, frame.height - 1), radius=22, fill=(12, 30, 50, 245), outline=ACCENT + (150,), width=2)
        frame.alpha_composite(img, (8, 8))
        base.alpha_composite(frame, xy)
    else:
        base.alpha_composite(img, xy)

def code_box(base, d, xy, lines, width=None, fsize=24):
    f = mono(fsize)
    lh = int(fsize * 1.5)
    maxw = max(textlen(d, l, f)[0] for l in lines) if lines else 200
    box_w = width or maxw + 64
    box_h = lh * len(lines) + 44
    panel(d, (xy[0], xy[1], xy[0] + box_w, xy[1] + box_h), radius=18, fill=(8, 20, 36))
    for i, line in enumerate(lines):
        color = (126, 196, 255) if line.strip().startswith(('bb_', '/', 'plugin')) else (210, 224, 238)
        if line.strip().startswith('#'):
            color = (116, 145, 170)
        d.text((xy[0] + 26, xy[1] + 22 + i * lh), line, font=f, fill=color)
    return box_h

def make_slide(page, total, section, builder):
    img = background().convert('RGBA')
    d = ImageDraw.Draw(img, 'RGBA')
    header(d, section)
    builder(img, d)
    footer(d, page, total)
    path = os.path.join(OUT, f'slide-{page:02d}.png')
    img.convert('RGB').save(path, quality=95)
    return path

# ------------------------------------------------------------------ slides
def slide_cover(img, d):
    d.text((88, 250), '让 AI 真正', font=font(84, True), fill=TEXT)
    d.text((88, 350), '走进 Blockbench', font=font(84, True), fill=(255, 255, 255))
    d.text((92, 480), '隐藏建模 · 无头渲染 · YSM 游戏验证', font=font(34), fill=(170, 211, 240))
    d.text((92, 540), '面向 DeepSeek Harness 的 Blockbench Agent 插件', font=font(24), fill=MUTED)
    x = 92
    for t, c in [('30 个语义工具', ACCENT), ('闭环渲染', (74, 222, 128)), ('YSM / Minecraft', (251, 191, 36))]:
        x = chip(d, x, 640, t, c) + 14
    d.text((92, 760), '“不是给 AI 一段建模步骤，', font=font(30), fill=(205, 226, 242))
    d.text((92, 808), '  而是让它真的看见自己做的模型。”', font=font(30), fill=(205, 226, 242))
    d.text((92, 930), '测试模型：DeepSeek 鲸鱼娘 · 蓝色大肥鱼', font=font(22), fill=(120, 165, 200))
    fish = load_asset('render-closeup.png')
    paste_float(img, fish, (1210, 215), 600, border=False)
    # accent ring
    ring = Image.new('RGBA', (760, 760), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse((30, 30, 730, 730), outline=ACCENT + (60,), width=3)
    rd.ellipse((90, 90, 670, 670), outline=ACCENT2 + (30,), width=1)
    img.alpha_composite(ring, (1090, 170))

def slide_problem(img, d):
    d.text((88, 235), '传统 AI 建模，', font=font(58, True), fill=TEXT)
    d.text((88, 305), '断在“最后一公里”', font=font(58, True), fill=(255, 145, 145))
    cards = [
        ('看不见', '只能输出命令和步骤，无法查看自己的渲染结果'),
        ('改不起', '改坏一次就崩，没有检查点、没有回滚'),
        ('存不下', 'YSM 包/贴图/动画不会自动保存与校验'),
    ]
    y = 440
    for i, (t, s) in enumerate(cards):
        panel(d, (88, y, 900, y + 128), radius=18)
        d.text((120, y + 24), f'0{i+1}', font=font(24, True), fill=(255, 120, 120))
        d.text((176, y + 20), t, font=font(34, True), fill=TEXT)
        draw_wrapped(d, (176, y + 70), s, font(23), MUTED, 690)
        y += 150
    fish = load_asset('render-front.png')
    paste_float(img, fish, (1120, 330), 540, border=False)
    d.text((1050, 890), '再漂亮的模型，AI 自己看不到，就只是盲盒。', font=font(26), fill=(255, 180, 160))

def slide_solution(img, d):
    d.text((88, 220), '把 AI 和 Blockbench 接成闭环', font=font(58, True), fill=TEXT)
    d.text((92, 300), 'DSH Blockbench Agent = dsh Host 插件 + 隐藏 Blockbench Runtime', font=font(26), fill=(150, 200, 235))
    boxes = [
        (88, 450, 388, 620, 'dsh / DeepSeek', '工具调用 · 多模态'),
        (500, 450, 800, 620, '隐藏 Blockbench', '后台 Electron · 不打扰'),
        (912, 450, 1212, 620, '无头渲染', '多机位 · 特写 · SSAA'),
        (1324, 450, 1624, 620, '自检 + 保存', 'watchdog · checkpoint'),
    ]
    for i, (x1, y1, x2, y2, t, s) in enumerate(boxes):
        panel(d, (x1, y1, x2, y2), radius=22, fill=(13, 34, 58))
        draw_wrapped(d, (x1 + 20, y1 + 28), t, font(24, True), TEXT, 260)
        draw_wrapped(d, (x1 + 20, y1 + 105), s, font(18), MUTED, 260, line_h=27)
        if i < 3:
            ax = x2 + 12
            d.line((ax, 535, ax + 88, 535), fill=ACCENT + (180,), width=3)
            d.polygon([(ax + 88, 535), (ax + 74, 526), (ax + 74, 544)], fill=ACCENT)
        # arrows back
    d.line((1624, 700, 1624, 780), fill=ACCENT2 + (180,), width=3)
    d.line((1624, 780, 388, 780), fill=ACCENT2 + (120,), width=3)
    d.polygon([(388, 780), (402, 771), (402, 789)], fill=ACCENT2)
    d.text((880, 725), '渲染图回流给模型 → 看得见结果再改', font=font(26), fill=(190, 170, 255))
    d.text((88, 860), '最终产物：YSM 工作区 / zip → 游戏内加载验证', font=font(24), fill=GREEN)

def slide_features(img, d):
    d.text((88, 220), '30 个工具，覆盖完整建模链路', font=font(56, True), fill=TEXT)
    d.text((92, 296), '全部通过 JSON-RPC 语义调用；一个操作一个 revision，失败可回滚', font=font(24), fill=(150, 195, 225))
    items = [
        ('建模', 'add_bone / add_cube / update / delete\ninflate · rotation · pivot'),
        ('贴图', 'pixel / rect / line / gradient\n图层 · PBR normal / specular'),
        ('动画', '动画 CRUD · 关键帧 · 控制器绑定'),
        ('渲染', '多机位 · closeup · SSAA\nwatchdog-v2 自检'),
        ('保存', 'checkpoint / restore · 增量写盘\n动画合并回写'),
        ('导出', 'YSM validate · zip 导出\n游戏内加载验证'),
    ]
    x0, y0 = 88, 390
    for i, (t, s) in enumerate(items):
        col, row = i % 3, i // 3
        x = x0 + col * 590
        y = y0 + row * 235
        panel(d, (x, y, x + 560, y + 200), radius=20)
        d.text((x + 28, y + 24), t, font=font(34, True), fill=ACCENT)
        draw_wrapped(d, (x + 28, y + 84), s, font(22), MUTED, 500, line_h=32)
    fish = load_asset('render-iso.png')
    paste_float(img, fish, (1480, 760), 260, border=False)

def slide_model(img, d):
    d.text((88, 220), '语义化建模：一次 patch 一个原子变更', font=font(52, True), fill=TEXT)
    lines = [
        'bb_apply_model_patch({',
        '  ops: [{',
        '    op: "add_cube", bone: "Head",',
        '    origin: [0, 42, 0], size: [2, 2, 2],',
        '    inflate: 1.5, rotation: [10, 20, 30],',
        '    uv: { mode: "faces", sizes: { north: [6, 6] } }',
        '  }]',
        '})',
    ]
    code_box(img, d, (88, 340), lines, fsize=25)
    bullets = [
        '骨骼 / 方块 / 尺寸 / 旋转 / 圆角',
        '一次 Undo、一个 revision、自动预算',
        '支持按面指定 UV 尺寸，贴图细节不糊',
    ]
    y = 720
    for b in bullets:
        d.ellipse((94, y + 10, 108, y + 24), fill=ACCENT)
        d.text((126, y), b, font=font(24), fill=(205, 225, 242))
        y += 58
    fish = load_asset('render-closeup.png')
    paste_float(img, fish, (1250, 230), 540, border=False)
    d.text((1230, 830), '目标：Q 版鲸鱼娘 / 大肥鱼', font=font(22), fill=(140, 180, 215))

def slide_texture(img, d):
    d.text((88, 220), '像素级贴图，不只是“换个颜色”', font=font(52, True), fill=TEXT)
    d.text((92, 296), '纹理坐标直接落在 128×128 画布上，AI 能看见局部、也能精确修改', font=font(24), fill=(150, 195, 225))
    lines = [
        'bb_texture_patch({ texture: "default", ops: [',
        '  { op: "rect", x1: 16, y1: 76, x2: 50, y2: 94,',
        '    color: "#f4f7fb" },',
        '  { op: "line", ... },',
        '  { op: "gradient", ... }',
        '] })',
    ]
    code_box(img, d, (88, 370), lines, fsize=24)
    tags = ['像素/矩形/线/渐变', '替换/镜像/图层', 'PBR _n / _s', '调色板统计']
    x, y = 92, 670
    for t in tags:
        x = chip(d, x, y, t, (116, 200, 255), 20) + 12
        if x > 820:
            x, y = 92, y + 56
    fish = load_asset('render-front.png')
    paste_float(img, fish, (1090, 235), 520, border=False)
    # swatches
    sw = ['#1b2a52', '#2f5a9e', '#6fb7e8', '#f4f7fb', '#e08a97']
    for i, c in enumerate(sw):
        d.rounded_rectangle((1120 + i * 50, 800, 1158 + i * 50, 838), radius=6, fill=c)
    d.text((1120, 856), 'DeepSeek 鲸鱼娘配色', font=font(20), fill=(140, 180, 215))

def slide_render(img, d):
    d.text((88, 220), '自己看，自己改', font=font(58, True), fill=TEXT)
    d.text((92, 300), '渲染结果回流给模型：不是“生成完就结束”，而是持续收敛', font=font(24), fill=(150, 195, 225))
    lines = [
        '{',
        '  "verdict": "no_visible_change",',
        '  "unchanged_streak": 3,',
        '  "checks": [{"id": "edit_visible", "status": "fail"}],',
        '  "suggestion": "bb_restore + change strategy"',
        '}',
    ]
    code_box(img, d, (88, 380), lines, fsize=23, width=740)
    tags = ['front / right / iso', 'closeup + SSAA', 'changed / alpha / bbox', 'edge_touch 裁切检测']
    x, y = 92, 700
    for t in tags:
        x = chip(d, x, y, t, (74, 222, 128), 19) + 12
        if x > 800:
            x, y = 92, y + 56
    fish = load_asset('render-closeup.png')
    paste_float(img, fish, (1120, 215), 560, border=False)
    d.text((1140, 840), '连续改不出可见变化 → watchdog 阻止空转', font=font(21), fill=(150, 220, 180))

def slide_anim(img, d):
    d.text((88, 220), '动画、控制器、检查点，一起管', font=font(54, True), fill=TEXT)
    cards = [
        ('动画', 'create / patch / delete\n关键帧 · 循环 · 时长', ACCENT),
        ('控制器', 'bind_controller\n状态 → 动画映射', (139, 124, 255)),
        ('检查点', '内嵌贴图 + arm 快照\nrestore 一键回滚', (74, 222, 128)),
        ('保存', '增量写盘 · 动画合并回写\n未改内容不重排', (251, 191, 36)),
    ]
    for i, (t, s, c) in enumerate(cards):
        x = 88 + (i % 2) * 610
        y = 360 + (i // 2) * 245
        panel(d, (x, y, x + 570, y + 205), radius=20)
        d.text((x + 28, y + 26), t, font=font(34, True), fill=c)
        draw_wrapped(d, (x + 28, y + 92), s, font(22), MUTED, 500, line_h=32)
    fish = load_asset('render-iso.png')
    paste_float(img, fish, (1410, 300), 330, border=False)
    d.text((1280, 860), '测试模型：deepseek-fish', font=font(20), fill=(130, 170, 205))

def slide_game(img, d):
    d.text((88, 205), '从工作区，到 Minecraft 游戏内', font=font(52, True), fill=TEXT)
    d.text((92, 280), '导出 YSM zip → custom 目录 → /ysm model reload → /ysm model set', font=font(23), fill=(150, 195, 225))
    shot = load_asset('ingame-set.png')
    if shot:
        shot.thumbnail((980, 620), Image.LANCZOS)
        frame = Image.new('RGBA', (shot.width + 16, shot.height + 16), (0, 0, 0, 0))
        fd = ImageDraw.Draw(frame)
        fd.rounded_rectangle((0, 0, frame.width - 1, frame.height - 1), radius=18, fill=(10, 24, 40, 245), outline=ACCENT + (130,), width=2)
        frame.alpha_composite(shot, (8, 8))
        img.alpha_composite(frame, (88, 350))
    steps = ['1. pack.zip', '2. YSM custom/', '3. reload', '4. set @s']
    y = 350
    for i, s in enumerate(steps):
        x = 1140
        panel(d, (x, y, x + 620, y + 90), radius=16, fill=(12, 30, 50))
        d.text((x + 24, y + 22), s, font=font(26, True), fill=(215, 232, 245))
        y += 112
    d.text((1140, 830), '日志确认：[YSM] Set \'deepseek_fish\' models', font=font(20), fill=GREEN)
    d.text((1140, 872), '第三人称 / 第一人称均可见', font=font(20), fill=(140, 180, 215))

def slide_safety(img, d):
    d.text((88, 220), '安全、可控、随时接管', font=font(56, True), fill=TEXT)
    items = [
        ('隐藏窗口', 'Blockbench 在后台运行，不抢焦点'),
        ('Revision 校验', '并发/旧 revision 自动拒绝，避免覆盖'),
        ('预算限制', '编辑/渲染/restore 都有上限'),
        ('/show /hide', '人要看时窗口出现，AI 自动暂停'),
        ('双传输', 'WebSocket 主链路 + HTTP/SSE 回退'),
        ('只读状态', 'Client pill / /bb-status 随时查看'),
    ]
    for i, (t, s) in enumerate(items):
        x = 88 + (i % 3) * 590
        y = 360 + (i // 3) * 215
        panel(d, (x, y, x + 560, y + 180), radius=18)
        d.text((x + 26, y + 24), t, font=font(28, True), fill=ACCENT)
        draw_wrapped(d, (x + 26, y + 80), s, font(21), MUTED, 500, line_h=30)
    d.text((700, 905), 'GUI 可见时写操作返回 GUI_BUSY，不会和用户抢模型', font=font(22), fill=(150, 200, 235))

def slide_compare(img, d):
    d.text((88, 220), '为什么不是另一个建模脚本？', font=font(54, True), fill=TEXT)
    rows = [
        ('传统 AI 对话 / 脚本', 'DSH Blockbench Agent'),
        ('看不见渲染结果', '无头多机位渲染 + 图片回流'),
        ('改坏无法回滚', 'checkpoint / restore / revision'),
        ('YSM 包保存不完整', '校验 + 增量保存 + zip 导出'),
        ('需要手动切窗口', '隐藏运行 + /show 随时接管'),
        ('游戏内验证靠人', '一键导出 → 游戏内加载验证'),
    ]
    x1, x2 = 88, 1060
    y = 350
    for i, (a, b) in enumerate(rows):
        if i == 0:
            d.text((x1 + 20, y), a, font=font(24, True), fill=MUTED)
            d.text((x2 + 20, y), b, font=font(24, True), fill=ACCENT)
            y += 56
            continue
        panel(d, (x1, y, x1 + 900, y + 76), radius=14, fill=(12, 28, 46))
        panel(d, (x2, y, x2 + 780, y + 76), radius=14, fill=(9, 34, 48), outline=(45, 110, 130), width=2)
        d.text((x1 + 24, y + 20), a, font=font(24), fill=(200, 210, 220))
        d.text((x2 + 24, y + 20), b, font=font(23, True), fill=(130, 235, 195))
        y += 88
    d.text((88, 930), '核心差别：闭环。看得到、改得动、存得下、能验证。', font=font(26), fill=(150, 200, 235))

def slide_start(img, d):
    d.text((88, 220), '3 分钟开始使用', font=font(58, True), fill=TEXT)
    lines = [
        '# 1. install bundle into current dsh profile',
        'plugin_manager install_bundle',
        '  target="<release>/dsh-blockbench-agent"',
        '',
        '# 2. open any session',
        '/bb-status',
        'load skill: blockbench-ysm-artist',
        '',
        '# 3. take over when needed: /show, /hide',
    ]
    code_box(img, d, (88, 350), lines, fsize=23, width=900)
    d.text((92, 830), 'GitHub：github.com/yan-mc/blockbench-ysm-agent', font=font(25), fill=ACCENT)
    d.text((92, 880), 'Release：v0.4.0 · 完整使用手册 MANUAL.md', font=font(23), fill=(150, 195, 225))
    d.text((92, 930), '测试模型：DeepSeek 鲸鱼娘 / 蓝色大肥鱼', font=font(21), fill=(120, 165, 200))
    fish = load_asset('render-closeup.png')
    paste_float(img, fish, (1230, 240), 500, border=False)
    # QR to repository
    try:
        import qrcode
        qr = qrcode.make('https://github.com/yan-mc/blockbench-ysm-agent')
        qr = qr.convert('RGB').resize((190, 190), Image.LANCZOS)
        qr = ImageOps.expand(qr, border=10, fill=(255, 255, 255))
        img.alpha_composite(qr.convert('RGBA'), (1250, 760))
        d.text((1470, 790), '仓库二维码', font=font(20), fill=(160, 205, 235))
        d.text((1470, 826), 'README / MANUAL', font=font(18), fill=(120, 165, 200))
    except Exception:
        d.rounded_rectangle((1250, 800, 1570, 900), radius=14, fill=(12, 30, 50), outline=(45, 90, 125), width=2)
        d.text((1270, 820), '扫码 / 搜索仓库', font=font(22), fill=(160, 205, 235))
        d.text((1270, 858), 'yan-mc/blockbench-ysm-agent', font=font(18), fill=(110, 150, 185))

slides = [
    ('01 · 开场', slide_cover),
    ('02 · 痛点', slide_problem),
    ('03 · 方案', slide_solution),
    ('04 · 能力', slide_features),
    ('05 · 建模', slide_model),
    ('06 · 贴图', slide_texture),
    ('07 · 渲染闭环', slide_render),
    ('08 · 动画与保存', slide_anim),
    ('09 · 游戏验证', slide_game),
    ('10 · 安全可控', slide_safety),
    ('11 · 优势', slide_compare),
    ('12 · 上手', slide_start),
]
paths = []
for i, (section, builder) in enumerate(slides):
    paths.append(make_slide(i, len(slides), section, builder))

# cover for GitHub (1280x640) + social (1280x640)
cover = background().resize((1280, 720)).convert('RGBA')
cd = ImageDraw.Draw(cover, 'RGBA')
cd.text((64, 90), 'DSH × Blockbench Agent', font=font(48, True), fill=(255, 255, 255))
cd.text((66, 170), '让 AI 真正走进 Blockbench', font=font(34, True), fill=(160, 220, 250))
cd.text((66, 230), '隐藏建模 · 无头渲染 · YSM 游戏验证', font=font(20), fill=(180, 205, 225))
cd.text((66, 300), '30 个语义工具 / 闭环自检 / checkpoint / 双传输', font=font(18), fill=(140, 175, 205))
fish = load_asset('render-front.png')
if fish:
    fish.thumbnail((300, 300), Image.LANCZOS)
    cover.alpha_composite(fish, (930, 260))
cd.text((66, 610), 'github.com/yan-mc/blockbench-ysm-agent', font=font(18), fill=(110, 180, 220))
cover.convert('RGB').save(os.path.join(DOCS_ASSETS, 'cover.png'), quality=95)
# social 1280x640 crop from cover
social = cover.crop((0, 0, 1280, 640)).convert('RGB')
social.save(os.path.join(DOCS_ASSETS, 'social-preview.png'), quality=95)
print(json.dumps({'slides': paths, 'cover': os.path.join(DOCS_ASSETS, 'cover.png')}, ensure_ascii=False, indent=2))
