"""Typography: project labels tracked to flying tiles + the end title. Returns premultiplied RGBA float."""
import os as _os
ROOT = _os.environ.get("GIRIH_ROOT", _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import json, math
from functools import lru_cache
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, features

FPS, W, H, SS = 30, 1920, 804, 3            # draw at 3x, downsample -> clean anti-aliasing
FONTS = ROOT + "/fonts/"
assert features.check("raqm"), "Persian shaping needs libraqm"

LABELS = [  # (start s, end s, tile, english, persian, side)
    (11.5, 13.3, "tile_220", "PersianVPN", "پرشین وی‌پی‌ان", "right"),
    (12.4, 14.2, "tile_364", "Persian Movies", "پرشین موویز", "right"),
    (13.3, 15.1, "tile_160", "MediaForge", "دانلودر تلگرام", "right"),
    (14.4, 16.2, "tile_226", "Bolgram", "درگاه پرداخت بلگرام", "left"),
    (15.1, 16.9, "tile_297", "Channel Mover", "انتقال کانال تلگرام", "right"),
    (16.0, 17.8, "tile_156", "Zagros Shop", "فروشگاه زاگرس", "right"),
]
TITLE_T0 = 18.6

@lru_cache(None)
def font(name, size):
    return ImageFont.truetype(FONTS + name, size * SS, layout_engine=ImageFont.Layout.RAQM)

@lru_cache(None)
def anchors():
    return json.load(open(ROOT + "/anchors.json"))["frames"]

def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)

def ease_out(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3

def tracked(draw, xy, text, fnt, fill, spacing):
    """Latin text with letter-spacing (in px at 1x)."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + spacing * SS
    return x

def tracked_width(draw, text, fnt, spacing):
    return sum(draw.textlength(ch, font=fnt) for ch in text) + spacing * SS * (len(text) - 1)

def draw_label(img, draw, f, lab):
    s0, s1, tile, en, fa, side = lab
    s = (f - 1) / FPS
    if not (s0 <= s <= s1):
        return
    t, dur = s - s0, s1 - s0
    out = 1.0 - smooth((t - (dur - 0.45)) / 0.45)
    x, y, z = anchors()[str(f)][tile]
    ax, ay = x * W * SS, (1 - y) * H * SS
    k = -1 if side == "left" else 1
    a_ring = ease_out(t / 0.3) * out
    a_line = ease_out((t - 0.12) / 0.35)
    a_text = smooth((t - 0.30) / 0.40) * out
    white = lambda a: (255, 255, 255, int(255 * a))
    # anchor: thin ring + centre dot
    r = (5 + 4 * (1 - ease_out(t / 0.3))) * SS
    draw.ellipse((ax - r, ay - r, ax + r, ay + r), outline=white(0.9 * a_ring), width=int(1.6 * SS))
    draw.ellipse((ax - 1.6 * SS, ay - 1.6 * SS, ax + 1.6 * SS, ay + 1.6 * SS), fill=white(0.9 * a_ring))
    # leader: diagonal then horizontal, drawn on progressively
    p0 = (ax + k * 7 * SS, ay - 7 * SS)
    p1 = (ax + k * 40 * SS, ay - 40 * SS)
    p2 = (p1[0] + k * 34 * SS, p1[1])
    seg1 = min(1.0, a_line / 0.55); seg2 = max(0.0, (a_line - 0.55) / 0.45)
    q1 = (p0[0] + (p1[0] - p0[0]) * seg1, p0[1] + (p1[1] - p0[1]) * seg1)
    lw = int(1.4 * SS)
    if seg1 > 0:
        draw.line([p0, q1], fill=white(0.75 * out), width=lw)
    if seg2 > 0:
        draw.line([p1, (p1[0] + (p2[0] - p1[0]) * seg2, p1[1])], fill=white(0.75 * out), width=lw)
    # text block
    fe, ff = font("InterDisplay-SemiBold.ttf", 27), font("Vazirmatn-Regular.ttf", 21)
    slide = (1 - ease_out((t - 0.30) / 0.5)) * 10 * SS
    we = tracked_width(draw, en, fe, 0.6)
    wf = draw.textlength(fa, font=ff, direction="rtl", language="fa")
    gap = 12 * SS
    if k > 0:
        xe, xf = p2[0] + gap + slide, p2[0] + gap + slide
    else:
        xe, xf = p2[0] - gap - we - slide, p2[0] - gap - wf - slide
    ye = p1[1] - 25 * SS
    tracked(draw, (xe, ye), en, fe, white(0.96 * a_text), 0.6)
    draw.text((xf, ye + 34 * SS), fa, font=ff, fill=white(0.72 * a_text), direction="rtl", language="fa")

def draw_title(img, draw, f):
    s = (f - 1) / FPS
    if s < TITLE_T0:
        return
    t = s - TITLE_T0
    end = 1.0 - smooth((s - 21.55) / 0.42)
    cx = 0.735 * W * SS
    def line_alpha(d):
        return smooth((t - d) / 0.9) * end
    def drift(d):
        return (1 - ease_out((t - d) / 1.4)) * 14 * SS
    # Persian headline
    fh = font("Vazirmatn-Light.ttf", 60)
    head = "داستان از اینجا شروع شد"
    wh = draw.textlength(head, font=fh, direction="rtl", language="fa")
    y0 = 0.36 * H * SS
    draw.text((cx - wh / 2, y0 + drift(0.0)), head, font=fh, fill=(255, 255, 255, int(255 * line_alpha(0.0))),
              direction="rtl", language="fa")
    # English subline, tracked caps
    fs = font("Inter-Medium.ttf", 17)
    sub = "THE STORY STARTS HERE"
    ws = tracked_width(draw, sub, fs, 6.0)
    tracked(draw, (cx - ws / 2, y0 + 104 * SS + drift(0.35)), sub, fs, (255, 255, 255, int(255 * 0.74 * line_alpha(0.35))), 6.0)
    # rule + signature
    a3 = line_alpha(0.85)
    ry = y0 + 152 * SS
    half = 64 * SS * ease_out((t - 0.85) / 1.0)
    if half > 1:
        draw.line([(cx - half, ry), (cx + half, ry)], fill=(255, 255, 255, int(255 * 0.45 * end)), width=int(1.2 * SS))
    fn = font("InterDisplay-SemiBold.ttf", 30)
    name = "alzhmd"
    wn = tracked_width(draw, name, fn, 4.0)
    tracked(draw, (cx - wn / 2, ry + 22 * SS + drift(0.95)), name, fn, (255, 255, 255, int(255 * a3)), 4.0)
    fu = font("Inter-Regular.ttf", 15)
    url = "github.com/alzhmd"
    wu = tracked_width(draw, url, fu, 1.2)
    tracked(draw, (cx - wu / 2, ry + 66 * SS + drift(1.1)), url, fu, (255, 255, 255, int(255 * 0.55 * line_alpha(1.1))), 1.2)

def overlay(f):
    s = (f - 1) / FPS
    active = [l for l in LABELS if l[0] <= s <= l[1]]
    if not active and s < TITLE_T0:
        return None
    img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for lab in active:
        draw_label(img, draw, f, lab)
    draw_title(img, draw, f)
    a = np.asarray(img).astype(np.float32) / 255.0
    a = cv2.resize(a, (W, H), interpolation=cv2.INTER_AREA)
    # soft shadow keeps thin type readable over bright glass
    sh = cv2.GaussianBlur(a[..., 3], (0, 0), 2.2) * 0.55
    rgb_pm = a[..., :3] * a[..., 3:4]
    alpha = 1 - (1 - a[..., 3]) * (1 - sh)
    return np.dstack([rgb_pm, alpha])
