"""Advantage slides for the shop screen (same frame as the rates board):
python make_slides.py -> slide_1.png .. slide_3.png, slide_glitch.png (2400x1000) + concept.png"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 2400, 1000
F = "/usr/share/fonts/opentype/inter/"
font = lambda n, s: ImageFont.truetype(F + n, s)
GREEN, MINT, WHITE, GREY = (25, 196, 138), (120, 255, 190), (232, 255, 244), (110, 130, 122)


def frame(idx):
    img = Image.new("RGB", (W, H), (4, 7, 6))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((14, 14, W - 14, H - 14), 28, outline=GREEN, width=6)
    d.text((80, 60), "EMERALD", font=font("InterDisplay-Bold.otf", 80), fill=GREEN)
    d.text((W - 80, 78), "WHY US", font=font("Inter-SemiBold.otf", 50), fill=GREY, anchor="ra")
    for k in range(3):                                   # progress dots
        x = W // 2 - 60 + k * 60
        d.rounded_rectangle((x - 18, H - 80, x + 18, H - 68), 6, fill=GREEN if k == idx else (30, 60, 48))
    return img, d


def glow(img):
    g = img.filter(ImageFilter.GaussianBlur(14))
    return Image.blend(img, Image.eval(g, lambda v: min(255, v * 2)), 0.3)


def bolt(d, cx, cy, s, fill):
    p = [(0.15, -1), (-0.55, 0.12), (-0.05, 0.12), (-0.2, 1), (0.55, -0.15), (0.05, -0.15), (0.3, -1)]
    d.polygon([(cx + x * s, cy + y * s) for x, y in p], fill=fill)


def shield(d, cx, cy, s, fill):
    p = [(0, -1), (0.8, -0.7), (0.75, 0.15), (0, 1), (-0.75, 0.15), (-0.8, -0.7)]
    d.polygon([(cx + x * s, cy + y * s) for x, y in p], fill=fill)
    d.line([(cx - 0.35 * s, cy), (cx - 0.05 * s, cy + 0.3 * s), (cx + 0.4 * s, cy - 0.3 * s)], fill=(4, 7, 6), width=int(s * 0.16))


slides = []
img, d = frame(0)
d.text((W // 2, 430), "75%", font=font("InterDisplay-Bold.otf", 430), fill=MINT, anchor="mm")
d.text((W // 2, 760), "ЛУЧШИЙ ПРОЦЕНТ", font=font("Inter-Bold.otf", 120), fill=WHITE, anchor="mm")
slides.append(glow(img))

img, d = frame(1)
bolt(d, W // 2, 380, 210, MINT)
d.text((W // 2, 690), "МОМЕНТАЛЬНЫЕ", font=font("Inter-Bold.otf", 150), fill=WHITE, anchor="mm")
d.text((W // 2, 840), "ВЫПЛАТЫ", font=font("Inter-Bold.otf", 110), fill=GREEN, anchor="mm")
slides.append(glow(img))

img, d = frame(2)
shield(d, W // 2 - 520, 470, 190, MINT)
d.text((W // 2 - 260, 470), "1+", font=font("InterDisplay-Bold.otf", 360), fill=MINT, anchor="lm")
d.text((W // 2 + 240, 470), "ГОД", font=font("InterDisplay-Bold.otf", 220), fill=WHITE, anchor="lm")
d.text((W // 2, 780), "РАБОТАЕМ БОЛЬШЕ ГОДА", font=font("Inter-Bold.otf", 110), fill=WHITE, anchor="mm")
slides.append(glow(img))

for i, s in enumerate(slides, 1):
    s.save(f"slide_{i}.png")

# glitch transition frame: horizontal slices shifted, RGB split, scanlines
a = np.asarray(slides[0]).astype(np.int16)
b = np.asarray(slides[1]).astype(np.int16)
rng = np.random.default_rng(4)
out = np.where((np.arange(H) // 40 % 3 == 0)[:, None, None], b, a).copy()
for y in range(0, H, 24):
    if rng.random() < 0.45:
        out[y:y + 24] = np.roll(out[y:y + 24], int(rng.integers(-160, 160)), axis=1)
out[..., 0] = np.roll(out[..., 0], 14, axis=1)
out[..., 2] = np.roll(out[..., 2], -14, axis=1)
out[::4] = out[::4] * 0.55
Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).save("slide_glitch.png")

sheet = Image.new("RGB", (1200 * 2 + 30, 500 * 2 + 30), (20, 20, 20))
for k, f in enumerate(["slide_1.png", "slide_glitch.png", "slide_2.png", "slide_3.png"]):
    sheet.paste(Image.open(f).resize((1200, 500)), ((k % 2) * 1230, (k // 2) * 530))
sheet.save("concept.png")
