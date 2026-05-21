"""
生成 7 个道具动画 .pak 文件 (v4 — 特效移至左下方，避免遮挡面部)
底图: icons/icon.png  每个道具 24 帧 @ 20fps
输出: assets/items/item_*.pak

布局原则:
  ✓ 道具物件出现在左下方（远离面部）
  ✓ FloatLabel 在右上方 → 与道具效果形成对角分布
  ✓ 粒子/爱心/星光向左/下扩散，不覆盖面部
  ✓ 每个道具保持独立的特效风格
"""
import io, math, os, sys, zipfile
from PIL import Image, ImageDraw, ImageFilter

# ── 路径 ─────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON = os.path.join(ROOT, "icons", "icon.png")
OUT  = os.path.join(ROOT, "assets", "items")
os.makedirs(OUT, exist_ok=True)

# ── pak 格式 ─────────────────────────────────────────────────────────
_MAGIC   = b'PTPAK\x01\x00\x00'
_XOR_KEY = b'\x54\x6f\x6e\x67\x50\x65\x74\x41\x6e\x69\x6d'
def _xor(data: bytes) -> bytes:
    if not data: return b''
    key, n = _XOR_KEY, len(data)
    fk = (key * (n // len(key) + 1))[:n]
    return (int.from_bytes(data, 'little') ^ int.from_bytes(fk, 'little')).to_bytes(n, 'little')

def save_pak(frames: list[Image.Image], name: str):
    path = os.path.join(OUT, f"{name}.pak")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, fr in enumerate(frames):
            fb = io.BytesIO()
            fr.save(fb, 'PNG', optimize=True)
            zf.writestr(f"{i:04d}.png", fb.getvalue())
    with open(path, 'wb') as f:
        f.write(_MAGIC + _xor(buf.getvalue()))
    print(f"  {name}.pak  {len(frames)} frames  {os.path.getsize(path) // 1024}KB")

# ── 画布参数 ─────────────────────────────────────────────────────────
SZ = 400
N  = 24

# 角色面部中心（要避开的区域）
FACE_X, FACE_Y = SZ // 2, int(SZ * 0.35)

# ★ 道具效果锚点：左下方，远离面部和右上方 FloatLabel
IX, IY = int(SZ * 0.18), int(SZ * 0.74)    # (72, 296)

base_raw = Image.open(ICON).convert('RGBA').resize((SZ, SZ), Image.LANCZOS)
def B():  return base_raw.copy()
def ov():
    img = Image.new('RGBA', (SZ, SZ), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)
def comp(b, o): return Image.alpha_composite(b, o)

# ── 缓动 ─────────────────────────────────────────────────────────────
def ease_out(t):    return 1.0 - (1.0 - min(1, max(0, t))) ** 3
def ease_in(t):     return min(1, max(0, t)) ** 2
def ease_inout(t):
    t = min(1, max(0, t))
    return 4*t*t*t if t < 0.5 else 1 - (-2*t + 2)**3 / 2
def lerp(a, b, t):  return a + (b - a) * t

def ma(f, fi=4, fo=5):
    """主透明度包络"""
    return min(1.0, f / max(1, fi)) * max(0.0, 1.0 - max(0, f - (N - fo)) / max(1, fo))

# ── 图形工具 ─────────────────────────────────────────────────────────
def circ(d, x, y, r, fill):
    if r < 1: return
    d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

def star5(d, cx, cy, r, fill):
    if r < 1: return
    pts = []
    for i in range(10):
        a = math.pi * i / 5 - math.pi / 2
        R = r if i % 2 == 0 else r * 0.38
        pts.append((cx + R * math.cos(a), cy + R * math.sin(a)))
    d.polygon(pts, fill=fill)

def heart(d, cx, cy, s, fill):
    if s < 2: return
    d.ellipse([cx - s/2, cy - s/3, cx, cy + s/8], fill=fill)
    d.ellipse([cx, cy - s/3, cx + s/2, cy + s/8], fill=fill)
    d.polygon([(cx - s/2 + 1, cy), (cx + s/2 - 1, cy), (cx, cy + s/2)], fill=fill)

def diamond(d, cx, cy, r, fill):
    if r < 1: return
    d.polygon([(cx, cy - r), (cx + r*0.6, cy), (cx, cy + r), (cx - r*0.6, cy)], fill=fill)

def soft_glow(color, x, y, r, alpha, blur_r=None):
    """返回一个高斯模糊柔光层 (SZ×SZ RGBA)"""
    g = Image.new('RGBA', (SZ, SZ), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    circ(d, int(x), int(y), int(r), (*color[:3], int(alpha)))
    return g.filter(ImageFilter.GaussianBlur(radius=blur_r or max(3, r * 0.7)))

def glow_dot(img, x, y, r, color, alpha):
    """发光粒子：三层同心渐变 + 高斯模糊，替代纯色 circ()，带光球质感。
    操作局部裁剪区域，避免全图 blur 的性能开销。"""
    if r < 1 or alpha < 5: return img
    x, y, r = int(x), int(y), int(r)
    pad = int(r * 2.6) + 4
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(SZ, x + pad), min(SZ, y + pad)
    if x1 <= x0 or y1 <= y0: return img
    w, h = x1 - x0, y1 - y0
    dot = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    dd  = ImageDraw.Draw(dot)
    lx, ly = x - x0, y - y0
    # 外光晕（大、透）
    circ(dd, lx, ly, int(r * 2.2), (*color[:3], int(alpha * 0.18)))
    # 中层
    circ(dd, lx, ly, int(r * 1.4), (*color[:3], int(alpha * 0.52)))
    # 亮核（混入白色，模拟自发光）
    wc = tuple(min(255, int(c * 0.55 + 255 * 0.45)) for c in color[:3])
    circ(dd, lx, ly, max(1, int(r * 0.65)), (*wc, min(255, int(alpha * 1.05))))
    dot = dot.filter(ImageFilter.GaussianBlur(radius=max(1.0, r * 0.45)))
    # 仅在裁剪区域做 alpha_composite
    region  = img.crop((x0, y0, x1, y1))
    merged  = Image.alpha_composite(region, dot)
    result  = img.copy()
    result.paste(merged, (x0, y0))
    return result

def cross_sparkle(d, cx, cy, r, fill):
    """✦ 十字闪光：4 主尖极长、4 间隙极短，比五角星更有光芒感"""
    if r < 2: return
    pts = []
    for i in range(8):
        angle = math.pi * i / 4 - math.pi / 2
        R = r if i % 2 == 0 else r * 0.12
        pts.append((cx + R * math.cos(angle), cy + R * math.sin(angle)))
    d.polygon(pts, fill=fill)

def waterdrop(d, cx, cy, r, fill):
    """水滴形：苹果独有的果汁飞溅形状"""
    if r < 2: return
    d.ellipse([cx - r, cy, cx + r, cy + r * 1.2], fill=fill)
    d.polygon([(cx - r * 0.45, cy + r * 0.15),
               (cx, cy - r * 1.4),
               (cx + r * 0.45, cy + r * 0.15)], fill=fill)

def hexagon(d, cx, cy, r, fill):
    """六角形：糖果独有的结晶体形状"""
    if r < 2: return
    pts = []
    for i in range(6):
        a = math.pi * i / 3 - math.pi / 6
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=fill)

# ═══════════════════════════════════════════════════════════════════
#  🍎 item_apple — 苹果从左上弧线坠落到左下 → 橙金色星光爆散
# ═══════════════════════════════════════════════════════════════════
def gen_apple():
    # 苹果落点: 左下
    AX_END, AY_END = IX + 10, IY - 5
    frames = []
    for f in range(N):
        img = B()

        # ── 柔光层（左下区域） ──
        glow = Image.new('RGBA', (SZ, SZ), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        m = ma(f, 3, 5)
        circ(gd, AX_END, AY_END, int(45 * m), (255, 180, 60, int(35 * m)))
        if 9 <= f <= 16:
            it = (f - 9) / 7.0
            circ(gd, AX_END, AY_END, int(55 * (1-it)), (255, 200, 80, int(45 * (1-it))))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=16))
        img = comp(img, glow)

        # ── 粒子层 ──
        o, d = ov()

        # 苹果从左上弧线坠落到左下
        if f <= 11:
            p = ease_out(f / 11.0)
            ax = int(lerp(SZ * 0.02, AX_END, p))
            ay = int(lerp(SZ * 0.40, AY_END, p))
        elif f <= 13:
            bounce = math.sin((f - 11) * math.pi / 2) * 10
            ax, ay = AX_END, int(AY_END - bounce)
        else:
            ax, ay = AX_END, AY_END

        aa = int(240 * ma(f, 2, 6))
        if aa > 5:
            R = int(SZ * 0.050)
            circ(d, ax, ay, R, (220, 42, 32, aa))
            circ(d, ax - 3, ay - 4, R - 4, (245, 75, 50, aa * 3 // 4))
            circ(d, ax - 5, ay - 6, R // 3, (255, 150, 130, aa // 2))
            d.line([(ax, ay-R), (ax+2, ay-R-8)], fill=(95, 60, 30, aa), width=2)
            circ(d, ax + 5, ay-R-4, 4, (70, 185, 50, aa))

        # ── 冲击白闪环（落地瞬间水平椭圆扩散） ──
        if 10 <= f <= 14:
            flash_t = (f - 10) / 4.0
            flash_r = int(SZ * 0.09 * ease_out(flash_t))
            flash_a = max(0, int(180 * (1 - flash_t)))
            if flash_a > 5:
                d.ellipse([AX_END - flash_r, AY_END - flash_r // 2,
                           AX_END + flash_r, AY_END + flash_r // 2],
                          outline=(255, 255, 255, flash_a), width=2)

        # 果汁飞溅粒子（向左下扩散）— glow_dot 发光版
        hero_sparks = []
        if f >= 10:
            t = (f - 10) / 13.0
            for i in range(12):
                ang   = math.pi * 0.4 + i * math.pi * 1.2 / 12 + i * 0.12
                speed = 0.7 + (i % 4) * 0.2
                dist  = ease_out(t) * SZ * 0.16 * speed
                px    = int(AX_END + math.cos(ang) * dist)
                py    = int(AY_END + math.sin(ang) * dist)
                pa    = max(0, int(200 * (1 - ease_in(t))))
                if pa > 5:
                    if i % 3 == 0:
                        # Hero 粒子：大发光球 + 记录位置留给 cross_sparkle
                        o = glow_dot(o, px, py, max(3, int(5*(1-t*0.35))), (255, 220, 50), pa)
                        hero_sparks.append((px, py, max(3, int(6*(1-t*0.4))), (255, 245, 140, pa)))
                    else:
                        # 普通粒子：中等发光球
                        col = (255, 170, 50) if i % 2 == 0 else (255, 140, 60)
                        o = glow_dot(o, px, py, max(2, int(3*(1-t*0.45))), col, pa)
        # cross_sparkle 在所有 glow_dot 之后绘制（刷新 d）
        d = ImageDraw.Draw(o)
        for (hx, hy, hr, hfill) in hero_sparks:
            waterdrop(d, hx, hy, hr, hfill)

        # ★ 标志细节：叶子从茎上飞离（落地后弹出，弧线向左上飘走）
        R_apple = int(SZ * 0.050)
        if f >= 11:
            lt = min(1.0, (f - 11) / 12.0)
            lx = int(AX_END + 5 - ease_out(lt) * 30)
            ly = int(AY_END - R_apple - 4 - ease_out(lt) * 28 + lt * lt * 18)
            la = max(0, int(230 * (1 - ease_in(lt))))
            if la > 5:
                lr = max(2, int(5 * (1 - lt * 0.25)))
                # 叶片椭圆
                d.ellipse([lx - lr*2, ly - lr, lx + lr*2, ly + lr],
                          fill=(65, 190, 50, la))
                # 叶脉中线
                d.line([(lx - lr*2 + 2, ly), (lx + lr*2 - 2, ly)],
                       fill=(100, 150, 40, la // 2), width=1)
                # 叶尖小高光点
                circ(d, lx + lr + 1, ly - 1, 1, (180, 240, 120, la // 2))

        frames.append(comp(img, o))
    return frames

# ═══════════════════════════════════════════════════════════════════
#  🍰 item_cake — 蛋糕从左边滑入左下 → 奶油溅射 → 金色满足光泡升腾
# ═══════════════════════════════════════════════════════════════════
def gen_cake():
    CK_X, CK_Y = IX + 5, IY - 10
    frames = []
    for f in range(N):
        img = B()

        glow = Image.new('RGBA', (SZ, SZ), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        m = ma(f, 3, 5)
        circ(gd, CK_X, CK_Y, int(45 * m), (255, 210, 110, int(30 * m)))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=18))
        img = comp(img, glow)

        o, d = ov()

        # 蛋糕从左侧滑入
        if f <= 8:
            p = ease_out(f / 8.0)
            ck_x = int(lerp(-SZ * 0.08, CK_X, p))
        else:
            ck_x = CK_X
        ck_y = CK_Y

        ca = int(230 * ma(f, 2, 5))
        if ca > 5:
            w, h = int(SZ*0.082), int(SZ*0.058)
            # 蛋糕底
            d.rounded_rectangle([ck_x-w, ck_y, ck_x+w, ck_y+h], radius=5,
                                fill=(255, 228, 205, ca))
            # 奶油层
            for i in range(5):
                wave_x = ck_x - w + i * (2 * w // 4)
                wave_y = ck_y - 3 + int(math.sin(i * 1.2 + f * 0.3) * 2)
                circ(d, wave_x, wave_y, 5, (255, 240, 245, ca))
            # 草莓
            circ(d, ck_x - 4, ck_y - 6, 5, (215, 40, 70, ca))
            circ(d, ck_x - 4, ck_y - 9, 2, (180, 210, 60, ca))
            # 蜡烛 + 火焰
            d.rectangle([ck_x + 7, ck_y - 16, ck_x + 10, ck_y - 3], fill=(255, 240, 110, ca))
            flicker = 0.7 + 0.3 * math.sin(f * 2.0)
            circ(d, ck_x + 8, ck_y - 19, 4, (255, 190, 40, int(ca * flicker)))
            circ(d, ck_x + 8, ck_y - 20, 2, (255, 255, 210, int(ca * flicker)))

        # 奶油飞溅（向左下飞溅）— glow_dot 柔光奶油点
        if 6 <= f <= 18:
            for i in range(5):
                sf = f - 6 - i
                if 0 <= sf < 10:
                    st = sf / 9.0
                    sx = int(CK_X - ease_out(st) * 25 - i * 6)
                    sy = int(CK_Y + ease_out(st) * 20 + i * 3)
                    sa = max(0, int(160 * (1 - st)))
                    if sa > 5:
                        o = glow_dot(o, sx, sy, max(2, int(4*(1-st*0.35))), (255, 240, 220), sa)
        d = ImageDraw.Draw(o)  # 刷新 d 供后续平面绘制

        # ★ 标志细节：彩色糖粉点（蛋糕到位后向四周散落）
        SPRINKLE_COLS = [(255, 60, 90), (60, 170, 255), (255, 210, 50),
                         (100, 225, 110), (220, 100, 255), (255, 140, 60)]
        if f >= 8:
            st = min(1.0, (f - 8) / 14.0)
            for i in range(11):
                col = SPRINKLE_COLS[i % len(SPRINKLE_COLS)]
                # 确定性伪随机角度 & 速度
                ang = i * 0.571 + 0.35 + (i % 3) * 0.18
                spd = 0.35 + (i * 17 % 10) / 10.0 * 0.40
                dist = ease_out(min(1.0, st * 1.6)) * SZ * 0.070 * spd
                sx = int(CK_X + math.cos(ang) * dist)
                sy = int(CK_Y + math.sin(ang) * dist + st * st * SZ * 0.025)
                sa = max(0, int(210 * (1 - ease_in(min(1.0, st * 0.75)))))
                if sa > 5:
                    # 交替画短条和圆点，更像真实糖粉
                    if i % 3 == 0:
                        d.ellipse([sx-2, sy-2, sx+2, sy+2], fill=(*col, sa))
                    else:
                        rot_a = i * 0.8
                        ex1 = int(sx + math.cos(rot_a) * 3)
                        ey1 = int(sy + math.sin(rot_a) * 3)
                        ex2 = int(sx - math.cos(rot_a) * 3)
                        ey2 = int(sy - math.sin(rot_a) * 3)
                        d.line([(ex1, ey1), (ex2, ey2)], fill=(*col, sa), width=2)

        # 金色满足光泡螺旋盘升（"香气盘旋"感，慵懒慢节奏）
        SATIS_COLS = [(255, 225, 130), (255, 205, 95), (250, 195, 75),
                      (255, 238, 160), (255, 215, 110)]
        for i in range(7):
            bf = f - 5 - i * 2.5          # 更大延迟 → 慵懒节奏
            if 0 <= bf < 15:
                bt = bf / 14.0
                # 螺旋路径：绕蛋糕上方做圆形运动 + 缓缓上升
                spiral_ang = bt * math.pi * 2.8 + i * 0.9
                spiral_r = SZ * 0.040 * (1 - bt * 0.3)
                bx = int(CK_X + math.cos(spiral_ang) * spiral_r)
                by = int(lerp(CK_Y - 22, SZ * 0.28, ease_out(bt)))
                ba = max(0, int(210 * (1 - ease_in(bt))))
                if ba > 5:
                    br = max(2, int(SZ * (0.014 + (i % 3) * 0.004)
                             * (0.60 + bt * 0.45)))
                    col = SATIS_COLS[i % len(SATIS_COLS)]
                    o = glow_dot(o, bx, by, br + 1, col, ba)
        d = ImageDraw.Draw(o)
        for i in range(7):
            bf = f - 5 - i * 2.5
            if 0 <= bf < 15:
                bt = bf / 14.0
                spiral_ang = bt * math.pi * 2.8 + i * 0.9
                spiral_r = SZ * 0.040 * (1 - bt * 0.3)
                bx = int(CK_X + math.cos(spiral_ang) * spiral_r)
                by = int(lerp(CK_Y - 22, SZ * 0.28, ease_out(bt)))
                ba = max(0, int(210 * (1 - ease_in(bt))))
                if ba > 5:
                    br = max(2, int(SZ * (0.014 + (i % 3) * 0.004)
                             * (0.60 + bt * 0.45)))
                    col = SATIS_COLS[i % len(SATIS_COLS)]
                    circ(d, bx, by, br, (*col, ba))
                    # 白色高光点（气泡质感）
                    circ(d, bx - max(1, br // 3), by - max(1, br // 3),
                         max(1, br // 3), (255, 255, 245, min(255, int(ba * 0.85))))
                    # 每 3 个加小白光点（气泡破裂光感）
                    if i % 3 == 0 and bt < 0.6:
                        circ(d, bx + 1, by - br - 1,
                             max(1, int(2 * (1 - bt * 0.5))),
                             (255, 255, 240, min(255, ba)))

        frames.append(comp(img, o))
    return frames

# ═══════════════════════════════════════════════════════════════════
#  🍬 item_candy — 彩色糖果粒在左下区域螺旋汇聚 → 闪光爆发
# ═══════════════════════════════════════════════════════════════════
def gen_candy():
    COLORS = [(255,80,120), (80,190,255), (255,210,50), (100,220,120), (210,130,255)]
    frames = []
    for f in range(N):
        img = B()

        glow = Image.new('RGBA', (SZ, SZ), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        m = ma(f, 4, 5)
        if f >= 10:
            bt = (f - 10) / 13.0
            circ(gd, IX, IY, int(55 * (1-bt) * m), (255, 230, 100, int(40 * (1-bt) * m)))
        circ(gd, IX, IY, int(30 * m), (255, 200, 80, int(20 * m)))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=14))
        img = comp(img, glow)

        # 彩虹旋转弧（糖果独有背景）
        if f >= 2:
            arc_layer = Image.new('RGBA', (SZ, SZ), (0, 0, 0, 0))
            ad = ImageDraw.Draw(arc_layer)
            arc_a = max(0, int(50 * m))
            if arc_a > 5:
                arc_r = int(SZ * 0.11)
                for ci, col in enumerate(COLORS):
                    start = int(ci * 72 + f * 15)
                    ad.arc([IX - arc_r, IY - arc_r, IX + arc_r, IY + arc_r],
                           start=start, end=start + 45,
                           fill=(*col, arc_a), width=2)
            arc_layer = arc_layer.filter(ImageFilter.GaussianBlur(radius=2))
            img = comp(img, arc_layer)

        o, d = ov()

        # 8 颗彩色糖果粒: 在左下区域螺旋汇聚/爆散
        n_candy = 8
        # 螺旋半径缩小（在左下局部区域内）
        for i in range(n_candy):
            col = COLORS[i % len(COLORS)]
            base_ang = i * math.pi * 2 / n_candy

            if f < 12:
                t = f / 12.0
                radius = lerp(SZ * 0.22, SZ * 0.03, ease_in(t))
                ang = base_ang + t * math.pi * 2.5
            else:
                t = (f - 12) / 11.0
                radius = lerp(SZ * 0.03, SZ * 0.20, ease_out(t))
                ang = base_ang + math.pi * 1.5 + t * math.pi * 0.8

            cx_ = int(IX + math.cos(ang) * radius)
            cy_ = int(IY + math.sin(ang) * radius)
            a = int(230 * m)

            if a > 5:
                r = int(SZ * 0.018 * (0.8 + 0.2 * math.sin(f * 1.2 + i)))
                # 主粒子 → glow_dot
                o = glow_dot(o, cx_, cy_, r, col, a)
                # 尾迹 → 小 glow_dot
                for t_i in range(3):
                    trail_f = max(0, f - t_i - 1)
                    if trail_f < 12:
                        tt = trail_f / 12.0
                        tr = lerp(SZ*0.22, SZ*0.03, ease_inout(tt))
                        ta = base_ang + tt * math.pi * 1.5
                    else:
                        tt = (trail_f - 12) / 11.0
                        tr = lerp(SZ*0.03, SZ*0.20, ease_out(tt))
                        ta = base_ang + math.pi*1.5 + tt*math.pi*0.8
                    tx   = int(IX + math.cos(ta) * tr)
                    ty   = int(IY + math.sin(ta) * tr)
                    ta_a = max(0, a // (t_i + 2))
                    if ta_a > 5:
                        o = glow_dot(o, tx, ty, max(1, r - t_i - 1), col, ta_a)

        d = ImageDraw.Draw(o)  # 刷新 d

        # 六角形轮廓叠加（糖果独有 — 结晶体形状）
        for i in range(n_candy):
            col = COLORS[i % len(COLORS)]
            base_ang = i * math.pi * 2 / n_candy
            if f < 12:
                t = f / 12.0
                radius = lerp(SZ * 0.22, SZ * 0.03, ease_in(t))
                ang = base_ang + t * math.pi * 2.5
            else:
                t = (f - 12) / 11.0
                radius = lerp(SZ * 0.03, SZ * 0.20, ease_out(t))
                ang = base_ang + math.pi * 1.5 + t * math.pi * 0.8
            cx_ = int(IX + math.cos(ang) * radius)
            cy_ = int(IY + math.sin(ang) * radius)
            a = int(190 * m)
            if a > 5:
                r = int(SZ * 0.018 * (0.8 + 0.2 * math.sin(f * 1.2 + i)))
                hexagon(d, cx_, cy_, r + 1, (*col, a))

        # 中心汇聚时的六角形闪光（糖果结晶爆发）
        if 10 <= f <= 15:
            sa = int(220 * m * (1.0 - (f - 10) / 5.0))
            if sa > 5:
                o = glow_dot(o, IX, IY, int(SZ*0.025), (255, 255, 200), sa)
                d = ImageDraw.Draw(o)
                hexagon(d, IX, IY, int(SZ*0.035), (255, 255, 240, sa))
                hexagon(d, IX, IY, int(SZ*0.020), (255, 255, 255, min(255, sa+30)))

        # ★ 标志细节：爆发后两圈白色能量扩散环（彩色描边，依次延迟）
        for ring_i in range(2):
            rf = f - 12 - ring_i * 3
            if 0 <= rf <= 10:
                rt = rf / 10.0
                rr = int(SZ * 0.035 + SZ * 0.14 * ease_out(rt))
                ra = max(0, int(170 * (1 - rt) * m))
                if ra > 5:
                    ring_col = (255, 255, 255) if ring_i == 0 else (255, 230, 120)
                    d.ellipse([IX-rr, IY-rr, IX+rr, IY+rr],
                              outline=(*ring_col, ra), width=2)

        frames.append(comp(img, o))
    return frames

# ═══════════════════════════════════════════════════════════════════
#  ☕ item_coffee — 咖啡杯从底部升起到左下 → 蒸汽左向卷曲 → 青色脉冲
# ═══════════════════════════════════════════════════════════════════
def gen_coffee():
    CUP_X, CUP_Y = IX + 12, IY - 5
    frames = []
    for f in range(N):
        img = B()

        glow = Image.new('RGBA', (SZ, SZ), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        m = ma(f, 3, 5)
        circ(gd, CUP_X, CUP_Y, int(38 * m), (60, 200, 210, int(28 * m)))
        if f >= 8:
            pt = (f - 8) / 15.0
            pr = int(25 + 55 * ease_out(pt))
            pa = max(0, int(35 * (1 - pt) * m))
            circ(gd, CUP_X, CUP_Y, pr, (80, 220, 230, pa))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=14))
        img = comp(img, glow)

        o, d = ov()

        # 杯子从底部升起
        if f <= 7:
            p = ease_out(f / 7.0)
            cup_y = int(lerp(SZ * 0.95, CUP_Y, p))
        else:
            cup_y = CUP_Y

        ca = int(235 * ma(f, 2, 5))
        if ca > 5:
            cw, ch = int(SZ*0.065), int(SZ*0.055)
            # 杯碟
            d.ellipse([CUP_X - cw - 3, cup_y + ch - 2, CUP_X + cw + 3, cup_y + ch + 5],
                      fill=(230, 222, 210, ca // 2))
            # 杯身
            d.rounded_rectangle([CUP_X-cw, cup_y, CUP_X+cw, cup_y+ch],
                                radius=4, fill=(242, 234, 224, ca))
            d.rounded_rectangle([CUP_X-cw+3, cup_y+3, CUP_X+cw-3, cup_y+ch-3],
                                radius=3, fill=(115, 72, 38, ca))
            # 咖啡液面
            d.ellipse([CUP_X-cw+4, cup_y+4, CUP_X+cw-4, cup_y+10],
                      fill=(145, 95, 55, ca * 2 // 3))
            # ★ 标志细节：液面白色弯月高光（左侧弧线，模拟光泽感）
            d.arc([CUP_X-cw+6, cup_y+5, CUP_X+2, cup_y+10],
                  start=200, end=345, fill=(255, 255, 245, int(ca * 0.72)), width=2)
            circ(d, CUP_X - cw//2 + 2, cup_y + 7, 1, (255, 255, 240, int(ca * 0.85)))
            # 把手（左侧，因为杯子在左下）
            d.arc([CUP_X-cw-12, cup_y+4, CUP_X-cw+2, cup_y+ch-4],
                  start=115, end=245, fill=(242, 234, 224, ca), width=3)

        # 蒸汽（向左上卷曲，不进入面部区域）
        if f >= 3:
            for i in range(3):
                sf = f - 3 - i * 2
                if sf < 0 or sf > 18: continue
                st = sf / 18.0
                sa = max(0, int(100 * (1 - ease_in(st)) * ma(f)))
                if sa < 5: continue
                x_base = CUP_X - 8 + (i - 1) * 8
                for step in range(10):
                    st2 = st + step * 0.005
                    py = int(lerp(cup_y - 3, SZ * 0.45, st2))
                    # 向左偏移的 S 形
                    amp = SZ * 0.015 * (1 + step * 0.12)
                    px = int(x_base - step * 1.5 + math.sin(step * 0.55 + sf * 0.35 + i * 1.2) * amp)
                    dot_a = max(0, int(sa * (1 - step / 10.0)))
                    if dot_a > 3:
                        dot_r = max(1, int(2 + step * 0.5))  # 越高越大→消散感
                        circ(d, px, py, dot_r, (255, 255, 255, dot_a))

        # 青色能量菱形火花（在杯子周围，偏左下）— glow_dot 底光 + diamond 形状
        if f >= 7:
            for i in range(5):
                sf = f - 7 - i * 2
                if 0 <= sf < 10:
                    st = sf / 9.0
                    ang  = math.pi * 0.3 + i * math.pi * 1.0 / 5 + 0.4
                    dist = SZ * 0.11 * ease_out(st)
                    ex   = int(CUP_X + math.cos(ang) * dist)
                    ey   = int(CUP_Y + math.sin(ang) * dist)
                    ea   = max(0, int(180 * (1 - st)))
                    if ea > 5:
                        sz = max(2, int(7 * (1 - st * 0.5)))
                        # 先画发光底层，再叠菱形轮廓
                        o = glow_dot(o, ex, ey, sz, (80, 220, 235), ea)
            d = ImageDraw.Draw(o)
            for i in range(5):
                sf = f - 7 - i * 2
                if 0 <= sf < 10:
                    st   = sf / 9.0
                    ang  = math.pi * 0.3 + i * math.pi * 1.0 / 5 + 0.4
                    dist = SZ * 0.11 * ease_out(st)
                    ex   = int(CUP_X + math.cos(ang) * dist)
                    ey   = int(CUP_Y + math.sin(ang) * dist)
                    ea   = max(0, int(180 * (1 - st)))
                    if ea > 5:
                        sz = max(2, int(7 * (1 - st * 0.5)))
                        diamond(d, ex, ey, sz, (200, 245, 255, ea))

        # 同心涟漪（从杯底向外扩散，水面波纹感 — 咖啡独有）
        if f >= 6:
            for ri in range(3):
                rf = f - 6 - ri * 4
                if 0 <= rf <= 12:
                    rt = rf / 12.0
                    rr = int(SZ * 0.02 + SZ * 0.10 * ease_out(rt))
                    ra = max(0, int(110 * (1 - rt) * m))
                    if ra > 5:
                        d.ellipse([CUP_X - rr, CUP_Y + 5 - rr // 3,
                                   CUP_X + rr, CUP_Y + 5 + rr // 3],
                                  outline=(180, 230, 240, ra), width=1)

        frames.append(comp(img, o))
    return frames

# ═══════════════════════════════════════════════════════════════════
#  🧸 item_plush — 玩偶从左侧滑入左下 → 发光爱心 + ✦ 闪光沿左侧升腾
# ═══════════════════════════════════════════════════════════════════
def gen_plush():
    BEAR_X, BEAR_Y = IX + 5, IY - 12
    frames = []
    for f in range(N):
        img = B()

        # 粉色柔光（左下区域）
        glow = Image.new('RGBA', (SZ, SZ), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        m = ma(f, 4, 5)
        circ(gd, BEAR_X, BEAR_Y, int(50 * m), (255, 140, 180, int(30 * m)))
        # 粉色 bokeh 光斑（限制在左下）
        for i in range(4):
            bx = int(IX - 15 + math.cos(i * 1.5 + f * 0.1) * 45)
            by = int(IY - 25 + math.sin(i * 1.0 + f * 0.15) * 35)
            circ(gd, bx, by, int(12 * m), (255, 180, 210, int(16 * m)))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=16))
        img = comp(img, glow)

        o, d = ov()

        # 玩偶从左侧滑入
        if f <= 9:
            p = ease_out(f / 9.0)
            bx = int(lerp(-SZ * 0.10, BEAR_X, p))
        else:
            bx = BEAR_X
        by = BEAR_Y

        ba = int(225 * ma(f, 2, 5))
        if ba > 5:
            # ★ 标志细节：玩偶身后粉色光晕圆（先画，让熊压在上面）
            aura_layer = Image.new('RGBA', (SZ, SZ), (0, 0, 0, 0))
            aura_draw  = ImageDraw.Draw(aura_layer)
            aura_r = int(SZ * 0.062)
            circ(aura_draw, bx, by - 4, aura_r,     (255, 160, 205, int(ba * 0.38)))
            circ(aura_draw, bx, by - 4, aura_r - 5, (255, 190, 220, int(ba * 0.22)))
            aura_layer = aura_layer.filter(ImageFilter.GaussianBlur(radius=10))
            o = Image.alpha_composite(o, aura_layer)
            d = ImageDraw.Draw(o)   # 刷新 draw 句柄

            # 熊头
            circ(d, bx, by - 12, int(SZ*0.045), (185, 135, 85, ba))
            # 耳朵
            for ex in [-12, 12]:
                circ(d, bx + ex, by - 24, 6, (185, 135, 85, ba))
                circ(d, bx + ex, by - 24, 3, (215, 175, 125, ba))
            # 身体
            circ(d, bx, by + 6, int(SZ*0.036), (185, 135, 85, ba))
            # 肚皮
            circ(d, bx, by + 7, int(SZ*0.020), (225, 195, 150, ba * 3 // 4))
            # 眼睛
            for ex in [-5, 5]:
                circ(d, bx + ex, by - 14, 2, (35, 25, 18, ba))
                circ(d, bx + ex - 1, by - 15, 1, (255, 255, 255, ba // 2))
            # 鼻子
            circ(d, bx, by - 9, 2, (125, 80, 50, ba))
            # 嘴巴
            d.arc([bx - 3, by - 8, bx + 3, by - 5], start=0, end=180,
                  fill=(125, 80, 50, ba), width=1)
            # 腮红
            circ(d, bx - 10, by - 8, 3, (255, 150, 165, ba // 2))
            circ(d, bx + 10, by - 8, 3, (255, 150, 165, ba // 2))

        # 爱心心跳脉冲（从玩偶中心向四周辐射 + 弹性缩放，像心跳节奏）
        HEART_COLS = [(255, 110, 155), (255, 165, 195), (255, 80, 130),
                      (255, 195, 215), (255, 130, 170)]
        HEART_SIZES = [0.024, 0.030, 0.022, 0.028, 0.020]
        n_hearts = 8
        # 第一遍：glow_dot 底光层
        for i in range(n_hearts):
            hf = f - 5 - i * 1.5
            if 0 <= hf < 17:
                ht = hf / 16.0
                # 从玩偶中心向四周辐射（不是全部向上！）
                h_ang = i * math.pi * 2 / n_hearts + 0.3
                h_dist = SZ * 0.025 + ease_out(ht) * SZ * 0.09
                hx = int(BEAR_X + math.cos(h_ang) * h_dist)
                hy = int(BEAR_Y - 5 + math.sin(h_ang) * h_dist)
                ha = max(0, int(210 * (1 - ease_in(ht))))
                if ha > 5:
                    s = int(SZ * HEART_SIZES[i % len(HEART_SIZES)])
                    col = HEART_COLS[i % len(HEART_COLS)]
                    o = glow_dot(o, hx, hy, s + 2, col, int(ha * 0.55))
        d = ImageDraw.Draw(o)
        # 第二遍：心形 + 弹性缩放 + ✦ 点缀
        for i in range(n_hearts):
            hf = f - 5 - i * 1.5
            if 0 <= hf < 17:
                ht = hf / 16.0
                h_ang = i * math.pi * 2 / n_hearts + 0.3
                h_dist = SZ * 0.025 + ease_out(ht) * SZ * 0.09
                hx = int(BEAR_X + math.cos(h_ang) * h_dist)
                hy = int(BEAR_Y - 5 + math.sin(h_ang) * h_dist)
                ha = max(0, int(210 * (1 - ease_in(ht))))
                if ha > 5:
                    base_s = int(SZ * HEART_SIZES[i % len(HEART_SIZES)])
                    # 弹性缩放：弹出 overshoot → 回弹 → 心跳脉冲
                    if ht < 0.15:
                        scale = ease_out(ht / 0.15) * 1.4
                    elif ht < 0.30:
                        scale = 1.4 - (ht - 0.15) / 0.15 * 0.4
                    else:
                        beat = math.sin((hf - 5) * math.pi / 3.0)
                        scale = 1.0 + max(0, beat) * 0.25
                    s = max(2, int(base_s * scale))
                    col = HEART_COLS[i % len(HEART_COLS)]
                    heart(d, hx, hy, s, (*col, ha))
                    # 奇数爱心旁加柔和白光点
                    if i % 2 == 1:
                        sp_x = hx + s // 2 + 3
                        sp_y = hy - s // 3
                        dot_r = max(1, int(2 * (1 - ht * 0.4)))
                        circ(d, sp_x, sp_y, dot_r,
                             (255, 255, 255, min(255, int(ha * 0.8))))

        frames.append(comp(img, o))
    return frames

# ═══════════════════════════════════════════════════════════════════
#  ⭐ item_star — 星群从四周涌入左下 → 金紫爆发 → 能量波扩散
# ═══════════════════════════════════════════════════════════════════
def gen_star():
    GOLD   = (255, 225, 60)
    PURPLE = (180, 130, 255)
    frames = []
    for f in range(N):
        img = B()

        # 金紫柔光（左下区域）
        glow = Image.new('RGBA', (SZ, SZ), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        m = ma(f, 3, 5)
        pulse = 0.7 + 0.3 * math.sin(f * 0.6)
        circ(gd, IX, IY, int(42 * m * pulse), (200, 160, 255, int(35 * m)))
        if 10 <= f <= 20:
            bt = (f - 10) / 10.0
            circ(gd, IX, IY, int(70 * ease_out(bt)), (255, 220, 100, int(30 * (1-bt) * m)))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=18))
        img = comp(img, glow)

        o, d = ov()

        # 10 颗星: 从四周涌向左下中心 → 爆发
        n_stars = 10
        for i in range(n_stars):
            base_ang = i * math.pi * 2 / n_stars + i * 0.2
            col = GOLD if i % 2 == 0 else PURPLE

            if f < 10:
                t = f / 10.0
                radius = lerp(SZ * 0.28, SZ * 0.02, ease_inout(t))
                ang = base_ang + t * math.pi * 0.6
            elif f < 14:
                t = (f - 10) / 4.0
                radius = SZ * 0.02 * (1 + math.sin(t * math.pi) * 0.5)
                ang = base_ang + math.pi * 0.6 + t * math.pi * 0.8
            else:
                t = (f - 14) / 9.0
                radius = lerp(SZ * 0.02, SZ * 0.25, ease_out(t))
                ang = base_ang + math.pi * 1.4 + t * math.pi * 0.4

            sx = int(IX + math.cos(ang) * radius)
            sy = int(IY + math.sin(ang) * radius)
            a  = int(230 * m)
            if a > 5:
                r = max(2, int(SZ * 0.016 * (0.7 + 0.3 * math.sin(f * 1.3 + i * 0.9))))
                # 主粒子 → glow_dot（金/紫发光球）
                o = glow_dot(o, sx, sy, r, col, a)
                # 尾迹 → 小 glow_dot
                for t_i in range(2):
                    prev_f = max(0, f - t_i - 1)
                    if prev_f < 10:
                        pt = prev_f / 10.0
                        pr = lerp(SZ*0.28, SZ*0.02, ease_inout(pt))
                        pa = base_ang + pt * math.pi * 0.6
                    elif prev_f < 14:
                        pt = (prev_f - 10) / 4.0
                        pr = SZ*0.02*(1+math.sin(pt*math.pi)*0.5)
                        pa = base_ang + math.pi*0.6 + pt*math.pi*0.8
                    else:
                        pt = (prev_f - 14) / 9.0
                        pr = lerp(SZ*0.02, SZ*0.25, ease_out(pt))
                        pa = base_ang + math.pi*1.4 + pt*math.pi*0.4
                    tx   = int(IX + math.cos(pa) * pr)
                    ty   = int(IY + math.sin(pa) * pr)
                    ta_a = max(0, a // (t_i + 3))
                    if ta_a > 5:
                        o = glow_dot(o, tx, ty, max(1, r - t_i - 1), col, ta_a)

        d = ImageDraw.Draw(o)  # 刷新 d

        # ── 汇聚蓄力闪光（戏剧停顿：汇聚→短暂蓄力→爆发） ──
        if 9 <= f <= 13:
            hold_t = (f - 9) / 4.0
            flash_a = max(0, int(220 * (1 - abs(hold_t - 0.35) * 1.8) * m))
            if flash_a > 5:
                flash_r = max(3, int(SZ * 0.03 * (1 + hold_t * 0.5)))
                o = glow_dot(o, IX, IY, flash_r + 2, (255, 255, 200), flash_a)
                d = ImageDraw.Draw(o)
                cross_sparkle(d, IX, IY, flash_r + 5,
                              (255, 255, 240, min(255, flash_a)))
                cross_sparkle(d, IX, IY, flash_r,
                              (255, 255, 255, min(255, flash_a + 30)))

        # 金色粒子（偶数索引）用 cross_sparkle 叠加在 glow 上方
        for i in range(n_stars):
            if i % 2 != 0: continue   # 只处理金色粒子
            base_ang = i * math.pi * 2 / n_stars + i * 0.2
            if f < 10:
                t2 = f / 10.0
                radius2 = lerp(SZ*0.28, SZ*0.02, ease_inout(t2))
                ang2 = base_ang + t2 * math.pi * 0.6
            elif f < 14:
                t2 = (f-10)/4.0
                radius2 = SZ*0.02*(1+math.sin(t2*math.pi)*0.5)
                ang2 = base_ang + math.pi*0.6 + t2*math.pi*0.8
            else:
                t2 = (f-14)/9.0
                radius2 = lerp(SZ*0.02, SZ*0.25, ease_out(t2))
                ang2 = base_ang + math.pi*1.4 + t2*math.pi*0.4
            sx2 = int(IX + math.cos(ang2)*radius2)
            sy2 = int(IY + math.sin(ang2)*radius2)
            a2  = int(200 * m)
            if a2 > 5:
                r2 = max(2, int(SZ*0.014*(0.7+0.3*math.sin(f*1.3+i*0.9))))
                cross_sparkle(d, sx2, sy2, r2+2, (*GOLD, a2))

        # 能量波扩散环（从左下中心扩散，半径限制避免到面部）
        if 11 <= f <= 22:
            rt = (f - 11) / 11.0
            ring_r = int(SZ * 0.03 + SZ * 0.18 * ease_out(rt))
            ring_a = max(0, int(160 * (1 - rt) * m))
            if ring_a > 5:
                d.ellipse([IX-ring_r, IY-ring_r, IX+ring_r, IY+ring_r],
                          outline=(*PURPLE, ring_a), width=2)
                r2 = int(ring_r * 0.6)
                a2 = ring_a * 2 // 3
                if a2 > 5:
                    d.ellipse([IX-r2, IY-r2, IX+r2, IY+r2],
                              outline=(*GOLD, a2), width=1)

        # ★ 标志细节：爆发后金色径向扫光（8 条光线从中心向外辐射）
        if 14 <= f <= 22:
            sweep_t = (f - 14) / 8.0
            n_rays = 8
            for ri in range(n_rays):
                ray_ang = ri * math.pi * 2 / n_rays + sweep_t * math.pi * 0.3
                ray_len = int(SZ * 0.13 * ease_out(sweep_t))
                ray_a   = max(0, int(110 * (1 - sweep_t) * m))
                if ray_a > 5 and ray_len > 3:
                    ex = int(IX + math.cos(ray_ang) * ray_len)
                    ey = int(IY + math.sin(ray_ang) * ray_len)
                    lw = max(1, int(2 * (1 - sweep_t)))
                    d.line([(IX, IY), (ex, ey)], fill=(*GOLD, ray_a), width=lw)
                    # 光线端头加小✦
                    tip_a = ray_a * 2 // 3
                    if tip_a > 5:
                        star5(d, ex, ey, max(2, int(4*(1-sweep_t))), (*GOLD, tip_a))

        frames.append(comp(img, o))
    return frames

# ═══════════════════════════════════════════════════════════════════
#  🎁 item_gift — 礼盒从底部升起到左下 → 开盖 → 彩虹星光向左下喷发
# ═══════════════════════════════════════════════════════════════════
def gen_gift():
    # ★ 标志细节：8色彩纸 + 白色 + 粉色，形状更多样
    CONFETTI = [(255,107,107), (255,166,64), (255,225,64),
                (107,224,132), (64,176,255), (192,107,255),
                (255, 255, 255),    # 白色彩纸
                (255, 130, 200)]    # 粉色彩纸
    GX, GY = IX + 10, IY - 8
    frames = []
    for f in range(N):
        img = B()

        # 彩虹柔光（左下区域）
        glow = Image.new('RGBA', (SZ, SZ), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        m = ma(f, 3, 5)
        if f >= 9:
            bt = (f - 9) / 14.0
            for ci, col in enumerate(CONFETTI):
                ang = math.pi * 0.3 + ci * math.pi * 1.0 / 6
                gx = int(GX + math.cos(ang) * 16 * bt)
                gy = int(GY + math.sin(ang) * 12 * bt)
                circ(gd, gx, gy, int(30 * (1 - bt * 0.5) * m), (*col, int(15 * (1-bt) * m)))
        circ(gd, GX, GY, int(30*m), (255, 200, 130, int(22*m)))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=16))
        img = comp(img, glow)

        o, d = ov()
        gw, gh = int(SZ*0.075), int(SZ*0.065)

        # 礼盒从底部升起（开盖前 2 帧微颤增加期待感）
        if f <= 7:
            p = ease_out(f / 7.0)
            gy_ = int(lerp(SZ*0.95, GY, p))
            gx_s = 0
        elif f <= 9:
            gy_ = GY
            gx_s = int(3 * math.sin(f * math.pi * 3.5))   # 高频左右抖
        else:
            gy_ = GY
            gx_s = 0

        ga = int(230 * ma(f, 2, 5))
        bx_ = GX + gx_s   # 应用微颤偏移
        if ga > 5:
            # 盒身
            d.rounded_rectangle([bx_-gw, gy_, bx_+gw, gy_+gh],
                                radius=4, fill=(225, 50, 50, ga))
            # 丝带
            d.rectangle([bx_-2, gy_, bx_+2, gy_+gh], fill=(255, 218, 60, ga))
            d.rectangle([bx_-gw, gy_+gh//2-2, bx_+gw, gy_+gh//2+2], fill=(255, 218, 60, ga))

            if f < 10:
                ly = gy_ - 4
                d.rounded_rectangle([bx_-gw-2, ly, bx_+gw+2, ly+7],
                                    radius=3, fill=(205, 38, 38, ga))
                # 蝴蝶结
                d.polygon([(bx_-7, ly-1), (bx_-2, ly+3), (bx_-2, ly-1)],
                          fill=(255, 218, 60, ga))
                d.polygon([(bx_+7, ly-1), (bx_+2, ly+3), (bx_+2, ly-1)],
                          fill=(255, 218, 60, ga))
                circ(d, bx_, ly, 3, (255, 218, 60, ga))
            else:
                # 盖子向左飞走
                lt = (f - 10) / 8.0
                ly = int(gy_ - 4 - ease_out(lt) * SZ * 0.12)
                la = max(0, int(ga * (1 - lt)))
                if la > 5:
                    lx_off = int(-ease_out(lt) * SZ * 0.06)
                    d.rounded_rectangle([bx_-gw-2+lx_off, ly, bx_+gw+2+lx_off, ly+7],
                                        radius=3, fill=(205, 38, 38, la))

        # 星光爆发（glow_dot 底光 + cross_sparkle/star5 混搭）
        hero_gift = []
        if f >= 10:
            t = (f - 10) / 13.0
            for i in range(12):
                ang   = math.pi * 0.2 + i * math.pi * 1.4 / 12 + i * 0.25
                speed = 0.6 + (i % 5) * 0.18
                dist  = ease_out(t) * SZ * 0.18 * speed
                sx    = int(GX + math.cos(ang) * dist)
                sy    = int(GY - 4 + math.sin(ang) * dist)
                sa    = max(0, int(215 * (1 - ease_in(t))))
                if sa > 5:
                    col = CONFETTI[i % len(CONFETTI)]
                    sr  = max(2, int(7 * (1 - t*0.4)))
                    # 所有粒子加 glow_dot 底光
                    o = glow_dot(o, sx, sy, sr, col, sa)
                    # 偶数：cross_sparkle，奇数：star5（混搭）
                    hero_gift.append((sx, sy, sr, col, sa, i % 2 == 0))
        d = ImageDraw.Draw(o)
        for (sx, sy, sr, col, sa, is_cross) in hero_gift:
            if is_cross:
                cross_sparkle(d, sx, sy, sr + 1, (*col, sa))
            else:
                # 径向飘带线（从盒子中心向外辐射，彩纸感）
                rot = math.atan2(sy - GY, sx - GX)
                lx1 = int(sx + math.cos(rot) * sr)
                ly1 = int(sy + math.sin(rot) * sr)
                lx2 = int(sx - math.cos(rot) * sr)
                ly2 = int(sy - math.sin(rot) * sr)
                d.line([(lx1, ly1), (lx2, ly2)],
                       fill=(*col, sa), width=max(1, sr // 2))

            # ★ 标志细节：多形状彩纸（矩形/菱形/圆点 交替，带重力）
            for i in range(12):
                cf = f - 10 - i * 0.7
                if 0 <= cf < 13:
                    ct = cf / 12.0
                    ang = math.pi * 0.25 + i * math.pi * 1.35 / 12 + i * 0.22
                    cx2 = int(GX + math.cos(ang) * SZ * 0.14 * ease_out(ct))
                    # 喷泉弧线：先向上喷射 → 重力回落
                    cy2 = int(GY - 4
                              - ease_out(ct) * SZ * 0.10    # 向上
                              + ct * ct * SZ * 0.18)         # 重力
                    ca2 = max(0, int(200 * (1 - ct * 0.65)))
                    if ca2 > 5:
                        col = CONFETTI[i % len(CONFETTI)]
                        shape = i % 3
                        if shape == 0:
                            # 矩形彩纸（旋转感通过错位模拟）
                            w2, h2 = 3 + i % 3, 2 + i % 2
                            d.rectangle([cx2-w2, cy2-h2, cx2+w2, cy2+h2], fill=(*col, ca2))
                        elif shape == 1:
                            # 菱形
                            diamond(d, cx2, cy2, 3 + i % 2, (*col, ca2))
                        else:
                            # 圆点
                            circ(d, cx2, cy2, 3, (*col, ca2))

        frames.append(comp(img, o))
    return frames

# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    targets = sys.argv[1:]
    ALL = [
        ("item_apple",  gen_apple),
        ("item_cake",   gen_cake),
        ("item_candy",  gen_candy),
        ("item_coffee", gen_coffee),
        ("item_plush",  gen_plush),
        ("item_gift",   gen_gift),
        ("item_star",   gen_star),
    ]
    print("=== 生成道具动画 .pak (v4) ===")
    print(f"底图: {ICON}")
    print(f"输出: {OUT}")
    print()
    for name, gen in ALL:
        if targets and name not in targets:
            continue
        frames = gen()
        save_pak(frames, name)
    print("\n全部完成！")
