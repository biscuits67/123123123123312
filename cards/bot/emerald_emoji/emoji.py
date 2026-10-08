"""Emerald custom emoji for message texts (parse_mode="HTML").

    from emerald_emoji import e
    caption = f"{e('check')} Заявка была принята"

e(name) gives <tg-emoji emoji-id="…">✅</tg-emoji> once ids.json exists (see upload_pack.py),
otherwise just the regular emoji, so texts work before the pack is uploaded.
"""
import json
from pathlib import Path

_HERE = Path(__file__).parent
FALLBACK: dict[str, str] = json.loads((_HERE / "manifest.json").read_text(encoding="utf-8"))
_ids_file = _HERE / "ids.json"
IDS: dict[str, str] = json.loads(_ids_file.read_text()) if _ids_file.exists() else {}


def e(name: str) -> str:
    emoji = FALLBACK[name]
    emoji_id = IDS.get(name)
    return f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>' if emoji_id else emoji
