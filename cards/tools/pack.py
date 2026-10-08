"""Convert the bot's PNG assets to high-quality JPEG and build emerald_cards.zip.
Run after `node tools/render.js`:  python3 tools/pack.py"""
import os
import zipfile
from pathlib import Path

from PIL import Image

CARDS = Path(__file__).resolve().parent.parent
ASSETS = CARDS / "bot" / "emerald_cards" / "assets"

for folder in ("bases", "static"):
    for png in (ASSETS / folder).glob("*.png"):
        Image.open(png).convert("RGB").save(png.with_suffix(".jpg"), "JPEG", quality=95, subsampling=0, optimize=True)
        png.unlink()

out = CARDS / "emerald_cards.zip"
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(CARDS / "bot"):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            src = Path(root) / f
            z.write(src, Path("emerald_bot_cards") / src.relative_to(CARDS / "bot"))
print(f"{out.name}: {out.stat().st_size / 1e6:.1f} MB")
