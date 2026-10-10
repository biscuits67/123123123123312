"""Advantage slides for the shop screen (same 2400x1000 frame as the rates board):
python make_slides.py -> slide_1.png .. slide_3.png, slide_glitch.png + concept.png

One clean layout for all three: icon tile on the left, a big value line, a label line, a thin divider,
brand bar on top, a segmented progress bar at the bottom. Soft vertical gradient, faint grid, light bloom."""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 2400, 1000
F = "/usr/share/fonts/opentype/inter/"
font = lambda n, s: ImageFont.truetype(F + n, s)
GREEN, MINT, WHITE, GREY, DIM = (25, 196, 138), (130, 255, 196), (238, 248, 243), (120, 140, 132), (28, 52, 43)
X0 = 560                                   # text column


def base(idx):
    y = np.linspace(0, 1, H)[:, None, None]
    bg = (np.array([6, 16, 12]) * (1 - y) + np.array([2, 6, 5]) * y) * np.ones((H, W, 3))
    img = Image.fromarray(bg.astype(np.uint8))
    d = ImageDraw.Draw(img)
    for gx in range(0, W, 80):
        d.line((gx, 0, gx, H), fill=(9, 22, 17))
    for gy in range(0, H, 80):
        d.line((0, gy, W, gy), fill=(9, 22, 17))
    d.rounded_rectangle((14, 14, W - 14, H - 14), 28, outline=GREEN, width=5)
    d.text((90, 92), "EMERALD", font=font("InterDisplay-Bold.otf", 64), fill=GREEN, anchor="lm")
    d.text((455, 94), "EXCHANGE", font=font("Inter-Medium.otf", 40), fill=GREY, anchor="lm")
    d.text((W - 90, 94), f"0{idx + 1} / 03", font=font("Inter-Medium.otf", 40), fill=GREY, anchor="rm")
    d.line((90, 160, W - 90, 160), fill=DIM, width=3)
    seg = (W - 180 - 2 * 24) // 3
    for k in range(3):
        x = 90 + k * (seg + 24)
        d.rounded_rectangle((x, H - 92, x + seg, H - 82), 5, fill=GREEN if k == idx else DIM)
    return img, d


def tile(d, kind):
    cx, cy, r = 300, 500, 150
    d.rounded_rectangle((cx - r, cy - r, cx + r, cy + r), 44, fill=(10, 34, 26), outline=GREEN, width=5)
    if kind == "percent":
        d.ellipse((cx - 70, cy - 78, cx - 18, cy - 26), outline=MINT, width=16)
        d.ellipse((cx + 18, cy + 26, cx + 70, cy + 78), outline=MINT, width=16)
        d.line((cx + 62, cy - 82, cx - 62, cy + 82), fill=MINT, width=20)
    elif kind == "bolt":
        p = [(18, -92), (-58, 12), (-6, 12), (-24, 92), (58, -14), (6, -14)]
        d.polygon([(cx + x, cy + y) for x, y in p], fill=MINT)
    else:
        p = [(0, -92), (78, -62), (72, 18), (0, 92), (-72, 18), (-78, -62)]
        d.polygon([(cx + x, cy + y) for x, y in p], fill=MINT)
        d.line([(cx - 34, cy + 2), (cx - 6, cy + 32), (cx + 40, cy - 26)], fill=(10, 34, 26), width=18, joint="curve")


def text_block(d, value, value_size, label, sub):
    d.text((X0, 455), value, font=font("InterDisplay-Bold.otf", value_size), fill=MINT, anchor="ls")
    d.text((X0 + 6, 640), label, font=font("Inter-Bold.otf", 104), fill=WHITE, anchor="ls")
    d.line((X0 + 6, 700, X0 + 220, 700), fill=GREEN, width=6)
    d.text((X0 + 6, 785), sub, font=font("Inter-Medium.otf", 54), fill=GREY, anchor="ls")


def bloom(img):
    g = img.filter(ImageFilter.GaussianBlur(18))
    return Image.blend(img, Image.eval(g, lambda v: min(255, int(v * 1.8))), 0.16)


content = [
    ("percent", "75%", 300, "ЛУЧШИЙ ПРОЦЕНТ", "самая выгодная ставка на рынке"),
    ("bolt", "МГНОВЕННО", 210, "МОМЕНТАЛЬНЫЕ ВЫПЛАТЫ", "без ожидания и задержек"),
    ("shield", "1+ ГОД", 300, "РАБОТАЕМ БОЛЬШЕ ГОДА", "стабильно и надёжно"),
]
slides = []
for i, (icon, value, vs, label, sub) in enumerate(content):
    img, d = base(i)
    tile(d, icon)
    text_block(d, value, vs, label, sub)
    img = bloom(img)
    img.save(f"slide_{i + 1}.png")
    slides.append(img)

# transition: a short, controlled glitch (a few displaced bands + slight RGB split + scanlines)
a, b = (np.asarray(s).astype(np.int16) for s in slides[:2])
rng = np.random.default_rng(2)
out = a.copy()
for y0 in sorted(rng.choice(np.arange(180, H - 140, 30), 7, replace=False)):
    h = int(rng.integers(18, 60))
    src = b if rng.random() < 0.5 else a
    out[y0:y0 + h] = np.roll(src[y0:y0 + h], int(rng.integers(-90, 90)), axis=1)
out[..., 0] = np.roll(out[..., 0], 6, axis=1)
out[..., 2] = np.roll(out[..., 2], -6, axis=1)
out[::3] = (out[::3] * 0.75).astype(np.int16)
Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save("slide_glitch.png")

sheet = Image.new("RGB", (1200 * 2 + 30, 500 * 2 + 30), (20, 20, 20))
for k, f in enumerate(["slide_1.png", "slide_glitch.png", "slide_2.png", "slide_3.png"]):
    sheet.paste(Image.open(f).resize((1200, 500), Image.LANCZOS), ((k % 2) * 1230, (k // 2) * 530))
sheet.save("concept.png")
