"""Phone screen for the avatar: a dark EMERALD wallet app, tall enough to scroll (tiles vertically).

    python make_screen.py OUT.png
"""
import math
import random
import sys

from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
W, H = 600, 1300
BG, CARD, GREEN, WHITE, GREY = (6, 12, 10), (16, 28, 24), (40, 230, 130), (235, 245, 240), (120, 140, 132)
FONT = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"
FONT_R = "/usr/share/fonts/opentype/inter/Inter-Regular.otf"


def f(size, bold=True):
    try:
        return ImageFont.truetype(FONT if bold else FONT_R, size)
    except OSError:
        return ImageFont.load_default()


im = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(im)
d.text((40, 40), "EMERALD", font=f(54), fill=GREEN)
d.text((40, 110), "EXCHANGE", font=f(26, False), fill=GREY)
# balance card
d.rounded_rectangle((30, 170, W - 30, 470), 28, fill=CARD)
d.text((60, 200), "Баланс", font=f(28, False), fill=GREY)
d.text((60, 240), "12 500 USDT", font=f(64), fill=WHITE)
d.text((60, 325), "+ 4.8% за неделю", font=f(28), fill=GREEN)
random.seed(7)
pts, v = [], 0.5
for i in range(40):
    v = min(0.95, max(0.05, v + random.uniform(-0.09, 0.12)))
    pts.append((60 + i * (W - 120) / 39, 450 - v * 70))
d.line(pts, fill=GREEN, width=5, joint="curve")
# operations list
rows = [("Выплата", "+ 1 200 USDT"), ("Обмен", "+ 850 USDT"), ("Выплата", "+ 2 300 USDT"),
        ("Перевод", "+ 640 USDT"), ("Обмен", "+ 1 750 USDT"), ("Выплата", "+ 980 USDT"),
        ("Обмен", "+ 3 100 USDT"), ("Выплата", "+ 1 450 USDT")]
y = 510
for name, amt in rows:
    d.rounded_rectangle((30, y, W - 30, y + 90), 20, fill=CARD)
    d.ellipse((50, y + 20, 100, y + 70), fill=(20, 70, 48))
    d.text((64, y + 26), "₮", font=f(30), fill=GREEN)
    d.text((120, y + 28), name, font=f(30, False), fill=WHITE)
    tw = d.textlength(amt, font=f(30))
    d.text((W - 60 - tw, y + 28), amt, font=f(30), fill=GREEN)
    y += 100
im.save(OUT)
print("saved", OUT, im.size)
