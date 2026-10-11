"""Textures for the scene dressing: python make_textures.py -> usdt_stencil.png (alpha), em_mat.png"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

F = "/usr/share/fonts/opentype/inter/"
rng = np.random.default_rng(5)

# ---- USDT stencil sprayed on the pallet wrap (1.8 x 1.2 m face -> 1800 x 1200 px)
W, H = 1800, 1200
m = Image.new("L", (W, H))
d = ImageDraw.Draw(m)
cx, cy, r = 360, 600, 250
d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)                    # coin
d.ellipse((cx - r + 26, cy - r + 26, cx + r - 26, cy + r - 26), fill=0)  # ring
# tether-style T: top bar, stem, and the flat ellipse band across the stem
d.rectangle((cx - 150, cy - 150, cx + 150, cy - 85), fill=255)
d.rectangle((cx - 42, cy - 150, cx + 42, cy + 175), fill=255)
d.ellipse((cx - 175, cy - 55, cx + 175, cy + 25), outline=255, width=26)
# stencil bridges (gaps) like a real spray stencil
for y in (cy - 118, cy + 60):
    d.rectangle((cx - 50, y, cx + 50, y + 10), fill=0)
f = ImageFont.truetype(F + "InterDisplay-Black.otf" if False else F + "InterDisplay-Bold.otf", 330)
d.text((700, 470), "USDT", font=f, fill=255, anchor="lm")
d.text((710, 800), "TETHER  ·  1 000 000", font=ImageFont.truetype(F + "Inter-Bold.otf", 92), fill=255, anchor="lm")
for x in (870, 1160, 1450):                                               # stencil bridges in the letters
    d.rectangle((x, 300, x + 12, 640), fill=0)
# spray: soft edges, overspray speckle, drips, worn patches
m = m.filter(ImageFilter.GaussianBlur(2.2))
a = np.asarray(m).astype(np.float32) / 255
speck = (rng.random((H, W)) < 0.012).astype(np.float32) * (np.asarray(m.filter(ImageFilter.GaussianBlur(26))) / 255 > 0.08)
a = np.maximum(a, speck * 0.8)
for _ in range(14):                                                       # drips under the letters
    x = int(rng.uniform(720, 1700)); y0 = int(rng.uniform(560, 640)); ln = int(rng.uniform(30, 140))
    if a[y0 - 5, x] > 0.5:
        a[y0:y0 + ln, x - 3:x + 4] = np.maximum(a[y0:y0 + ln, x - 3:x + 4], np.linspace(0.9, 0, ln)[:, None])
wear = np.asarray(Image.fromarray((rng.random((H // 40, W // 40)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)) / 255
a *= np.clip(0.55 + wear * 0.7, 0, 1)
rgb = np.zeros((H, W, 3), np.uint8)
rgb[:] = (38, 161, 123)                                                   # tether green
Image.fromarray(np.dstack([rgb, (np.clip(a, 0, 1) * 255).astype(np.uint8)]), "RGBA").save("usdt_stencil.png")

# ---- entrance mat: black rubber, green EM monogram + EMERALD
W, H = 1200, 2000
img = Image.new("RGB", (W, H), (10, 11, 11))
d = ImageDraw.Draw(img)
d.rounded_rectangle((40, 40, W - 40, H - 40), 40, outline=(24, 150, 96), width=14)
d.text((W // 2, H // 2 - 120), "EM", font=ImageFont.truetype(F + "InterDisplay-Bold.otf", 520), fill=(24, 170, 106), anchor="mm")
d.text((W // 2, H // 2 + 300), "EMERALD", font=ImageFont.truetype(F + "Inter-Bold.otf", 150), fill=(200, 215, 208), anchor="mm")
noise = (rng.normal(0, 6, (H, W, 1))).astype(np.int16)
img = Image.fromarray(np.clip(np.asarray(img).astype(np.int16) + noise, 0, 255).astype(np.uint8))
img.save("em_mat.png")
