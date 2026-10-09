"""Exchange-rate board texture for the shop niche: python rates_board.py -> rates_board.png (2400x1000)."""
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 2400, 1000
F = "/usr/share/fonts/opentype/inter/"
font = lambda name, size: ImageFont.truetype(F + name, size)
GREEN, MINT, WHITE, GREY, RED = (25, 196, 138), (120, 255, 190), (232, 255, 244), (110, 130, 122), (255, 90, 90)

img = Image.new("RGB", (W, H), (4, 7, 6))
d = ImageDraw.Draw(img)
d.rounded_rectangle((14, 14, W - 14, H - 14), 28, outline=GREEN, width=6)
d.text((80, 60), "EMERALD", font=font("InterDisplay-Bold.otf", 96), fill=GREEN)
d.text((560, 86), "EXCHANGE  ·  RATES", font=font("Inter-SemiBold.otf", 58), fill=WHITE)
d.text((W - 80, 86), "24 / 7", font=font("Inter-SemiBold.otf", 58), fill=MINT, anchor="ra")
d.line((80, 210, W - 80, 210), fill=(25, 70, 52), width=4)
cols = (80, 1150, 1650, 2320)
hdr = font("Inter-Medium.otf", 44)
for x, t, a in zip(cols, ("PAIR", "BUY", "SELL", "24H"), ("la", "ra", "ra", "ra")):
    d.text((x if a == "la" else x, 240), t, font=hdr, fill=GREY, anchor=a)
rows = [("BTC / USDT", "64 210", "64 480", "+2.1%"), ("ETH / USDT", "3 120", "3 138", "+1.3%"),
        ("SOL / USDT", "148.6", "149.4", "+3.2%"), ("TON / USDT", "5.42", "5.49", "−0.6%")]
big, mono = font("Inter-Bold.otf", 84), font("Inter-SemiBold.otf", 84)
for i, (p, b, s, ch) in enumerate(rows):
    y = 330 + i * 160
    d.text((cols[0], y), p, font=big, fill=WHITE)
    d.text((cols[1], y), b, font=mono, fill=MINT, anchor="ra")
    d.text((cols[2], y), s, font=mono, fill=MINT, anchor="ra")
    d.text((cols[3], y), ch, font=mono, fill=RED if ch.startswith("−") else GREEN, anchor="ra")
    if i < len(rows) - 1:
        d.line((80, y + 128, W - 80, y + 128), fill=(18, 40, 32), width=2)
# soft LED bloom baked in
glow = img.filter(ImageFilter.GaussianBlur(10))
img = Image.blend(img, Image.eval(glow, lambda v: min(255, v * 2)), 0.25)
img.save("rates_board.png")
