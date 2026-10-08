import io
import json
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS = Path(__file__).parent / "assets"

FONTS = {
    "bold": "InterDisplay-Bold.otf",
    "semibold": "InterDisplay-SemiBold.otf",
    "medium": "InterDisplay-Medium.otf",
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
        _draw_slot(img, slot, clean(values[name]), spec["scale"], theme)
    buf = io.BytesIO()
    if fmt.upper() == "PNG":
        img.save(buf, "PNG", optimize=False, compress_level=3)
    else:
        img.save(buf, "JPEG", quality=95, subsampling=0, optimize=True)
    return buf.getvalue()
