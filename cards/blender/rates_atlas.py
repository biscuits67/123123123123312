"""Live rates board: 10 price ticks x (flash, settled) = 20 board states in one 4x5 atlas.

    python rates_atlas.py -> rates_atlas.png (4800x2500, each state 1200x500)

The scene steps through the states with a Mapping node (constant keys every 12-13 frames), so the
board ticks like a real exchange screen: changed prices flash green (up) or red (down), then settle.
The last tick returns to the first prices, so the 250-frame loop has no seam.
"""
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, COLS, ROWS = 1200, 500, 4, 5
F = "/usr/share/fonts/opentype/inter/"
font = lambda name, size: ImageFont.truetype(F + name, size)
GREEN, MINT, WHITE, GREY, RED = (25, 196, 138), (120, 255, 190), (232, 255, 244), (110, 130, 122), (255, 90, 90)
PAIRS = [("BTC / USDT", 64210, 0), ("ETH / USDT", 3120, 0), ("SOL / USDT", 148.6, 1), ("TON / USDT", 5.42, 2)]
SPREAD = (1.0042, 1.0058, 1.0054, 1.0129)
rng = random.Random(3)


def fmt(v, dec):
    return f"{v:,.{dec}f}".replace(",", " ")


# 10 ticks of a random walk that closes back on itself
ticks = [[p[1] for p in PAIRS]]
for t in range(1, 10):
    prev = ticks[-1]
    ticks.append([v * (1 + rng.uniform(-0.0035, 0.0035)) if rng.random() < 0.7 else v for v in prev])
ticks[-1] = [(a + b) / 2 for a, b in zip(ticks[-2], ticks[0])]   # glide home before the loop restarts
change24 = [2.1, 1.3, 3.2, -0.6]


def board(vals, prev, flash):
    S = 2  # draw at 2x, downsample for crisp text
    img = Image.new("RGB", (W * S, H * S), (4, 7, 6))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((7 * S, 7 * S, W * S - 7 * S, H * S - 7 * S), 14 * S, outline=GREEN, width=3 * S)
    d.text((40 * S, 30 * S), "EMERALD", font=font("InterDisplay-Bold.otf", 48 * S), fill=GREEN)
    d.text((280 * S, 43 * S), "EXCHANGE  ·  RATES", font=font("Inter-SemiBold.otf", 29 * S), fill=WHITE)
    d.text((W * S - 40 * S, 43 * S), "LIVE", font=font("Inter-SemiBold.otf", 29 * S), fill=MINT, anchor="ra")
    d.ellipse(((W - 120) * S, 52 * S, (W - 106) * S, 66 * S), fill=(255, 70, 70))
    d.line((40 * S, 105 * S, W * S - 40 * S, 105 * S), fill=(25, 70, 52), width=2 * S)
    cols = (40, 575, 825, 1160)
    for x, t, a in zip(cols, ("PAIR", "BUY", "SELL", "24H"), ("la", "ra", "ra", "ra")):
        d.text((x * S, 120 * S), t, font=font("Inter-Medium.otf", 22 * S), fill=GREY, anchor=a)
    big = font("Inter-Bold.otf", 42 * S)
    for i, ((name, _, dec), v, pv) in enumerate(zip(PAIRS, vals, prev)):
        y = 165 * S + i * 80 * S
        up, moved = v > pv, abs(v - pv) > 1e-9
        if flash and moved:
            d.rounded_rectangle((330 * S, y - 8 * S, 840 * S, y + 56 * S), 8 * S,
                                fill=(10, 70, 40) if up else (80, 18, 18))
        col = (GREEN if up else RED) if (flash and moved) else MINT
        d.text((cols[0] * S, y), name, font=big, fill=WHITE)
        d.text((cols[1] * S, y), fmt(v, dec), font=big, fill=col, anchor="ra")
        d.text((cols[2] * S, y), fmt(v * SPREAD[i], dec), font=big, fill=col, anchor="ra")
        ch = change24[i] + (v / PAIRS[i][1] - 1) * 100
        d.text((cols[3] * S, y), f"{'+' if ch >= 0 else '−'}{abs(ch):.1f}%", font=big, fill=GREEN if ch >= 0 else RED, anchor="ra")
        if flash and moved:
            d.text((292 * S, y + 6 * S), "▲" if up else "▼", font=font("Inter-Bold.otf", 26 * S),
                   fill=GREEN if up else RED)
        if i < 3:
            d.line((40 * S, y + 64 * S, W * S - 40 * S, y + 64 * S), fill=(18, 40, 32), width=S)
    img = img.resize((W, H), Image.LANCZOS)
    glow = img.filter(ImageFilter.GaussianBlur(6))
    return Image.blend(img, Image.eval(glow, lambda v: min(255, v * 2)), 0.22)


atlas = Image.new("RGB", (W * COLS, H * ROWS))
for t in range(10):
    for k, flash in enumerate((True, False)):
        n = t * 2 + k
        atlas.paste(board(ticks[t], ticks[t - 1], flash), ((n % COLS) * W, (n // COLS) * H))
atlas.save("rates_atlas.png", optimize=True)
