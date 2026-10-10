"""Realistic EU-style vanity plates: python make_plates.py -> plate_EMERALD.png, plate_TEAM.png (2080x440 = 520x110 mm)
plus plate_*_height.png for embossing (Bump node). White retro-reflective base, blue EU band, condensed black letters
with a stamped bevel, two screws, light road grime towards the bottom edge."""
import math
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W, H = 2080, 440
BAND = 180
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def letters(text):
    """Black condensed letters as a mask, FE-Schrift-like proportions (squeezed DejaVu Bold)."""
    f = ImageFont.truetype(FONT, 330)
    l, t, r, b = f.getbbox(text)
    m = Image.new("L", (r - l + 40, b - t + 40))
    ImageDraw.Draw(m).text((20 - l, 20 - t), text, font=f, fill=255)
    w = int(m.width * 0.78)
    spare = W - BAND - 160
    if w > spare:
        w = spare
    m = m.resize((w, int(m.height * 0.95)), Image.LANCZOS)
    full = Image.new("L", (W, H))
    full.paste(m, (BAND + (W - BAND - m.width) // 2, (H - m.height) // 2 + 6))
    return full


def plate(text):
    rng = np.random.default_rng(len(text))
    base = np.full((H, W, 3), (236, 237, 233), np.float32)
    # retro-reflective micro texture
    base += rng.normal(0, 2.2, (H, W, 1))
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((6, 6, W - 6, H - 6), 34, outline=(20, 20, 20), width=12)                # black rim
    d.rounded_rectangle((18, 18, BAND, H - 18), 22, fill=(0, 51, 153))                         # EU band
    for k in range(12):
        a = 2 * math.pi * k / 12
        cx, cy = 99 + 52 * math.cos(a), 150 + 52 * math.sin(a)
        pts = [(cx + rr * math.cos(-math.pi / 2 + j * math.pi / 5), cy + rr * math.sin(-math.pi / 2 + j * math.pi / 5))
               for j, rr in zip(range(10), [12, 5] * 5)]                                     # filled 5-point star
        d.polygon(pts, fill=(255, 204, 0))
    d.text((99, 330), "EM", font=ImageFont.truetype(FONT, 88), fill=(255, 255, 255), anchor="mm")
    m = letters(text)
    # stamped letters: dark face + light top-left edge + shadow bottom-right
    hi = ImageChops.offset(m, -3, -3)
    sh = ImageChops.offset(m, 4, 4).filter(ImageFilter.GaussianBlur(2))
    img.paste((150, 150, 150), (0, 0), ImageChops.subtract(sh, m))
    img.paste((18, 18, 18), (0, 0), m)
    img.paste((90, 90, 90), (0, 0), ImageChops.subtract(m, ImageChops.offset(m, 3, 3)).point(lambda v: v // 2))
    # screws
    for x in (BAND + 110, W - 110):
        d.ellipse((x - 22, 34, x + 22, 78), fill=(170, 172, 170), outline=(90, 90, 90), width=3)
        d.line((x - 13, 56, x + 13, 56), fill=(80, 80, 80), width=5)
    # grime: darker towards the bottom, a few splashes
    a = np.asarray(img).astype(np.float32)
    y = np.linspace(0, 1, H)[:, None, None]
    grime = 1 - 0.12 * y ** 2.5 - 0.05 * (rng.random((H // 8, W // 8, 1)).repeat(8, 0).repeat(8, 1)[:H, :W] * y)
    a *= grime
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    img.save(f"plate_{text}.png")
    m.filter(ImageFilter.GaussianBlur(3)).save(f"plate_{text}_height.png")


for t in ("EMERALD", "TEAM"):
    plate(t)
