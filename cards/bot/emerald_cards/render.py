import io
import json
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).parent / "assets"

FONTS = {
    "bold": "InterDisplay-Bold.otf",
}
THEMES = {
    "emerald": {"c1": (111, 242, 189), "c2": (25, 196, 138)},
    "ruby": {"c1": (255, 154, 166), "c2": (240, 71, 93)},
}
WHITE = (234, 255, 246)
MUTED = (143, 184, 167)
MIN_SIZE = 12

# Emoji and other symbols Inter has no glyphs for (they would render as boxes).
_UNSUPPORTED = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U0000FE00-\U0000FE0F\U0000200D\U000020E3\U0000E000-\U0000F8FF]"
)


@lru_cache(maxsize=None)
def _layout() -> dict:
    return json.loads((ASSETS / "layout.json").read_text("utf-8"))


@lru_cache(maxsize=None)
def _base(name: str) -> Image.Image:
    return Image.open(ASSETS / "bases" / f"{name}.png").convert("RGB")


@lru_cache(maxsize=64)
def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ASSETS / "fonts" / FONTS.get(weight, FONTS["bold"])), size)


def clean(text) -> str:
    text = _UNSUPPORTED.sub("", str(text))
    return re.sub(r"\s+", " ", text).strip()


def _fit(text: str, weight: str, size: int, max_w: int):
    """Shrink the font until the text fits; if it still doesn't, cut it with an ellipsis."""
    size = int(size)
    font = _font(weight, size)
    while font.getlength(text) > max_w and size > MIN_SIZE:
        size -= 1
        font = _font(weight, size)
    if font.getlength(text) > max_w:
        while text and font.getlength(text + "…") > max_w:
            text = text[:-1]
        text = text.rstrip() + "…"
    return text, font


def _gradient(w: int, h: int, c1, c2) -> Image.Image:
    """Horizontal c1 -> c2 -> c1 gradient, like the titles on the cards."""
    row = Image.new("RGB", (w, 1))
    px = row.load()
    for x in range(w):
        t = x / max(w - 1, 1)
        k = t / 0.55 if t < 0.55 else 1 - (t - 0.55) / 0.45
        px[x, 0] = tuple(round(a + (b - a) * k) for a, b in zip(c1, c2))
    return row.resize((w, h))


def _draw_slot(img: Image.Image, slot: dict, text: str, scale: float, theme: dict):
    x, y = round(slot["x"] * scale), round(slot["y"] * scale)
    w, h = round(slot["w"] * scale), round(slot["h"] * scale)
    text, font = _fit(text, slot.get("weight") or "bold", slot["size"] * scale, w)
    style = slot.get("style") or "white"
    if style == "grad":
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).text((0, h / 2), text, font=font, fill=255, anchor="lm")
        tw = max(1, min(w, round(font.getlength(text))))
        fill = Image.new("RGB", (w, h))
        fill.paste(_gradient(tw, h, theme["c1"], theme["c2"]), (0, 0))
        img.paste(fill, (x, y), mask)
    else:
        color = MUTED if style == "muted" else WHITE
        ImageDraw.Draw(img).text((x, y + h / 2), text, font=font, fill=color, anchor="lm")


def _draw_list(img: Image.Image, slot: dict, value, scale: float, theme: dict):
    """Rows of domains; the active one is highlighted. value = (items, active)."""
    items, active, all_active = value
    items = [clean(i) for i in items]
    active = clean(active) if active else None
    sc = scale
    x, y = slot["x"] * sc, slot["y"] * sc
    w, h = slot["w"] * sc, slot["h"] * sc
    row_h, gap, r = 56 * sc, 10 * sc, 14 * sc
    c1, c2 = theme["c1"], theme["c2"]
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    font = _font("bold", round(slot["size"] * sc))
    small = _font("bold", round(13 * sc))
    num_font = _font("bold", round(15 * sc))

    if not items:
        d.rounded_rectangle([x, y, x + w, y + row_h * 1.6], r, fill=(255, 255, 255, 12),
                            outline=(255, 255, 255, 30), width=max(1, round(sc)))
        d.text((x + 28 * sc, y + row_h * 0.8), "Домены не добавлены", font=font, fill=MUTED, anchor="lm")
        img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))
        return

    max_rows = max(1, int((h + gap) // (row_h + gap)))
    rows = list(enumerate(items, 1))
    more = 0
    if len(rows) > max_rows:
        visible = rows[: max_rows - 1]
        if active in items and all(t != active for _, t in visible):
            visible[-1] = next(rt for rt in rows if rt[1] == active)
        more = len(rows) - len(visible)
        rows = visible

    badge = "АКТИВНЫЙ"
    badge_w = small.getlength(badge) + 24 * sc
    for i, (n, text) in enumerate(rows):
        y0 = y + i * (row_h + gap)
        cy = y0 + row_h / 2
        on = text == active
        check = on or all_active
        d.rounded_rectangle([x, y0, x + w, y0 + row_h], r,
                            fill=(*c2, 38) if on else (255, 255, 255, 12),
                            outline=(*c2, 120) if on else (255, 255, 255, 26), width=max(1, round(sc)))
        d.text((x + 22 * sc, cy), f"{n:02d}", font=num_font, fill=(*MUTED, 200), anchor="lm")
        ix = x + 72 * sc
        if check:
            d.ellipse([ix - 11 * sc, cy - 11 * sc, ix + 11 * sc, cy + 11 * sc], fill=(*c2, 255))
            d.line([(ix - 5 * sc, cy), (ix - 1.5 * sc, cy + 4 * sc), (ix + 5.5 * sc, cy - 4 * sc)],
                   fill=(2, 20, 14, 255), width=max(2, round(3 * sc)), joint="curve")
        else:
            d.ellipse([ix - 8 * sc, cy - 8 * sc, ix + 8 * sc, cy + 8 * sc],
                      outline=(*MUTED, 160), width=max(1, round(2 * sc)))
        tx = x + 100 * sc
        max_w = (x + w - 20 * sc - (badge_w + 16 * sc if on else 0)) - tx
        t, f = _fit(text, "bold", slot["size"] * sc, max_w)
        d.text((tx, cy), t, font=f, fill=(*(WHITE if on else (200, 225, 214)), 255), anchor="lm")
        if on:
            bx1 = x + w - 18 * sc
            bx0 = bx1 - badge_w
            d.rounded_rectangle([bx0, cy - 15 * sc, bx1, cy + 15 * sc], 15 * sc, fill=(*c1, 40))
            d.text(((bx0 + bx1) / 2, cy), badge, font=small, fill=(*c1, 255), anchor="mm")
    if more:
        y0 = y + len(rows) * (row_h + gap)
        d.text((x + 22 * sc, y0 + row_h / 2), f"+ ещё {more}", font=num_font, fill=(*MUTED, 255), anchor="lm")
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))


def render(card: str, fmt: str = "JPEG", **values) -> bytes:
    """Draw values onto a dynamic card and return image bytes.

    card   -- name from assets/layout.json (e.g. "payout_amount")
    values -- slot name -> text (e.g. balance="1 234.56 $")
    """
    spec = _layout()[card]
    img = _base(card).copy()
    theme = THEMES[spec.get("theme", "emerald")]
    for name, slot in spec["slots"].items():
        if name not in values:
            raise TypeError(f"card {card!r} needs value {name!r}")
        if slot.get("kind") == "list":
            _draw_list(img, slot, values[name], spec["scale"], theme)
        else:
            _draw_slot(img, slot, clean(values[name]), spec["scale"], theme)
    buf = io.BytesIO()
    if fmt.upper() == "PNG":
        img.save(buf, "PNG", optimize=False, compress_level=3)
    else:
        img.save(buf, "JPEG", quality=95, subsampling=0, optimize=True)
    return buf.getvalue()
