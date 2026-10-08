"""Uploads the Emerald animated emoji as a Telegram custom emoji pack and saves their ids.

    BOT_TOKEN=123:abc OWNER_ID=111222333 python3 -m emerald_emoji.upload_pack

OWNER_ID is your Telegram user id (the pack is created on your account; you must have
started the bot once). Running it again adds emoji that are missing from the pack.
The result is ids.json next to this file — emoji.py reads it.
"""
import asyncio
import json
import os
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InputSticker

HERE = Path(__file__).parent
TITLE = "Emerald"


def sticker(name: str, emoji: str) -> InputSticker:
    return InputSticker(sticker=FSInputFile(HERE / "tgs" / f"{name}.tgs"), format="animated", emoji_list=[emoji])


async def main() -> None:
    manifest: dict[str, str] = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    bot = Bot(os.environ["BOT_TOKEN"])
    owner = int(os.environ["OWNER_ID"])
    me = await bot.get_me()
    set_name = os.environ.get("PACK_NAME", "emerald") + f"_by_{me.username}"
    ids_file = HERE / "ids.json"
    ids: dict[str, str] = json.loads(ids_file.read_text()) if ids_file.exists() else {}

    try:
        pack = await bot.get_sticker_set(set_name)
    except TelegramBadRequest:  # no such pack yet
        names = list(manifest)
        await bot.create_new_sticker_set(owner, set_name, TITLE, [sticker(n, manifest[n]) for n in names],
                                         sticker_type="custom_emoji")
        pack = await bot.get_sticker_set(set_name)
        ids = {n: s.custom_emoji_id for n, s in zip(names, pack.stickers)}
    else:
        known = set(ids.values())
        if {s.custom_emoji_id for s in pack.stickers} - known:
            raise SystemExit(f"{set_name} has emoji that are not in ids.json — delete the pack in @Stickers "
                             "or restore ids.json, then run again")
        for name in [n for n in manifest if n not in ids]:     # one by one to learn each new id
            await bot.add_sticker_to_set(owner, set_name, sticker(name, manifest[name]))
            pack = await bot.get_sticker_set(set_name)
            ids[name] = pack.stickers[-1].custom_emoji_id

    ids_file.write_text(json.dumps(ids, indent=1))
    print(f"https://t.me/addemoji/{set_name} — {len(ids)} emoji, ids saved to {ids_file.name}")
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
