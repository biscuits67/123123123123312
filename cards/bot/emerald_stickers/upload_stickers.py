"""Uploads the Emerald sticker pack (Эмик) to Telegram.

    BOT_TOKEN=123:abc OWNER_ID=111222333 python3 -m emerald_stickers.upload_stickers

OWNER_ID is your Telegram user id (you must have started the bot). Running it again adds the
stickers that are missing from the pack. Prints the t.me/addstickers/... link.
"""
import asyncio
import json
import os
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InputSticker

HERE = Path(__file__).parent
TITLE = "Emerald — Эмик"


def sticker(name: str, emoji: str) -> InputSticker:
    return InputSticker(sticker=FSInputFile(HERE / "webp" / f"{name}.webp"), format="static", emoji_list=[emoji])


async def main() -> None:
    manifest: dict[str, str] = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    bot = Bot(os.environ["BOT_TOKEN"])
    owner = int(os.environ["OWNER_ID"])
    me = await bot.get_me()
    set_name = os.environ.get("PACK_NAME", "emerald_emik") + f"_by_{me.username}"
    added_file = HERE / "uploaded.json"
    added: list[str] = json.loads(added_file.read_text()) if added_file.exists() else []

    try:
        await bot.get_sticker_set(set_name)
    except TelegramBadRequest:  # no such pack yet
        names = list(manifest)
        await bot.create_new_sticker_set(owner, set_name, TITLE, [sticker(n, manifest[n]) for n in names[:50]])
        added = names[:50]
    for name in [n for n in manifest if n not in added]:
        await bot.add_sticker_to_set(owner, set_name, sticker(name, manifest[name]))
        added.append(name)

    added_file.write_text(json.dumps(added, indent=1))
    print(f"https://t.me/addstickers/{set_name} — {len(added)} stickers")
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
