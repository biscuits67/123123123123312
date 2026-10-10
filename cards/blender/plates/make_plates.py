"""Vanity plates for the scene cars: python make_plates.py -> plate_EMERALD.png, plate_TEAM.png (2080x440, 520x110 mm)."""
from PIL import Image, ImageDraw, ImageFont

F = "/usr/share/fonts/opentype/inter/"
W, H = 2080, 440
for text in ("EMERALD", "TEAM"):
    img = Image.new("RGB", (W, H), (10, 12, 11))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((10, 10, W - 10, H - 10), 40, outline=(215, 225, 220), width=14)
    d.rounded_rectangle((34, 34, 210, H - 34), 22, fill=(16, 120, 72))           # emerald brand strip
    d.text((122, H // 2 + 40), "EM", font=ImageFont.truetype(F + "Inter-Bold.otf", 70), fill=(235, 245, 240), anchor="mm")
    d.polygon([(122, 95), (160, 140), (122, 185), (84, 140)], fill=(120, 255, 190))  # little gem
    size = 300 if len(text) > 5 else 330
    f = ImageFont.truetype(F + "InterDisplay-Bold.otf", size)
    d.text(((W + 210) // 2, H // 2 + 8), text, font=f, fill=(25, 196, 138), anchor="mm")
    img.save(f"plate_{text}.png")
