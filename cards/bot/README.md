# Emerald cards for the bot

`emerald_cards/` is a self-contained folder: copy it next to your bot and `pip install pillow`.

| Function | Message | Type |
|---|---|---|
| `cards.static("application_accepted")` | ✅ Заявка была принята | image file |
| `cards.application_rejected(admin_username)` | ❌ Заявка была отклонена | drawn: admin |
| `cards.static("wallet_trx")` | 💳 Выберите кошелек TRX | image file |
| `cards.static("nickname")` | ⭐️ Введите новый ник | image file |
| `cards.wallet_address(wallet_name)` | 💳 Введите новый адрес {wallet_name} кошелька | drawn: wallet |
| `cards.static("payout_choose")` | 💸 На какой кошелек заказать выплату? | image file |
| `cards.static("payout_done")` | ✅ Выплата совершена | image file |
| `cards.static("payout_rejected")` | ❌ Выплата отклонена | image file |
| `cards.payout_no_wallet(wallet)` | ❌ Укажите {wallet} кошелек для выплаты | drawn: wallet |
| `cards.payout_amount(balance)` | 💸 Введите сумму выплаты ⚡️ Доступно | drawn: balance |
| `cards.branch_info(members, turnover, percent)` | 👥 Участников / 💰 Оборот / 📊 Процент | drawn: stats |
| `cards.static("forum_link")` | 👍 Отправьте ссылку на профиль форума | image file |
| `cards.static("application_sent")` | ✈️ Ваша заявка успешно отправлена | image file |
| `cards.static("application_failed")` | ⛔️ Ваша заявка не была отправлена | image file |
| `cards.nickname_saved(nick)` | ✅ Новый ник успешно сохранен | drawn: nick |
| `cards.static("enter_number")` | ❌ Введите число | image file |
| `cards.static("promo_name")` | 💬 Введите название промокода | image file |
| `cards.static("promo_exists")` | ❌ Данный промокод уже существует | image file |
| `cards.static("domain_bad_format")` | ❌ Неверный формат домена | image file |
| `cards.domain_added(domain)` | ✅ Домен {domain} добавлен | drawn: domain |
| `cards.domain_exists(domain)` | ❌ Домен {domain} уже существует | drawn: domain |
| `cards.domains_list(domains, active_domain)` | 🔗 Актуальные домены (admin, active highlighted) | drawn: list |
| `cards.domains_list(active_domains, all_active=True)` | 🔗 Актуальные домены (menu) | drawn: list |
| `cards.static("domains_not_found")` | ❌ Активные домены не найдены | image file |
| `cards.static("menu_materials")` | 📕 Материалы | image file |
| `cards.static("menu_info")` | ℹ️ Информация | image file |
| `cards.static("top_deposits")` | 🥇 Выберите период для топа депозитов | image file |
| `cards.top_deposits(period, rows)` | 📅 Топ депозитов за день / неделю / месяц / всё время | drawn: top 5 |
| `cards.static("add_domain")` | 💬 Введите домен (example.com) | image file |
| `cards.static("cancelled")` | Операция отменена | image file |
| `cards.static("confirmed")` | Операция подтверждена | image file |
| `cards.static("unknown_command")` | Неизвестная команда | image file |
| `cards.static("banned")` | ⛔️ Вы были заблокированы администрацией | image file |
| `cards.static("profile_error")` | ⛔️ Ошибка профиля | image file |

Static cards are JPEG files. Dynamic functions return JPEG bytes (~80 ms per card) — send them with
`BufferedInputFile(data, "emerald.jpg")`. See `example_aiogram.py`.

The domains list shows up to 5 rows; the rest becomes «+ ещё N» (the active domain is always shown).
Long values shrink to fit and are cut with `…` if needed; emoji in names are removed
(the brand font has no emoji glyphs).

## Changing the design
Everything is drawn from `../card.html`. After editing it run `node ../tools/render.js`
(needs Playwright), then `python3 ../tools/pack.py` — they re-render the preview PNGs, the static cards and the
backgrounds + `layout.json` used by the Python code.

# Emerald animated emoji

`emerald_emoji/` holds 25 animated custom emoji in the same style as the cards: an emerald-cut stone
with a white icon, a light glint and sparkles. They're 3-second loops in Telegram's `.tgs` format
(100×100, 60 fps, ~1.5 KB each). Negative actions use a ruby stone and ratings/money use gold.
Frame 0 is always the complete icon, so the emoji also reads correctly when animations are off.
Preview: `../emoji_preview.gif`.

`owner` is a one-off emoji for the project owners: a clean monoline crown polished from emerald,
with a faceted emerald in the centre. Light runs along the lines, the stone flashes, the crown floats
on a soft emerald glow and sparkles appear around it. Preview: `../emoji_owner.gif`.
`royal` is the brand emerald wearing that crown. The crown hops up and lands on the stone with a
little squash, the stone flexes and glows brighter, and light runs over the stone and then the crown.
Preview: `../emoji_royal.gif`.

The other crown designs we tried can be generated with `python3 ../tools/emoji_build.py --owner-variants`.

| name | emoji | | name | emoji | | name | emoji |
|---|---|---|---|---|---|---|---|
| `gem` | 💎 | | `coin` | 💰 | | `info` | ℹ️ |
| `check` | ✅ | | `chart` | 📊 | | `medal` | 🥇 |
| `cross` | ❌ | | `like` | 👍 | | `crown` | 👑 |
| `stop` | ⛔ | | `plane` | ✈️ | | `calendar` | 📅 |
| `wallet` | 💳 | | `chat` | 💬 | | `globe` | 🌐 |
| `star` | ⭐ | | `link` | 🔗 | | `hourglass` | ⏳ |
| `payout` | 💸 | | `book` | 📕 | | `bell` | 🔔 |
| `bolt` | ⚡ | | `users` | 👥 | | **`owner`** | 👑 |
| | | | | | | **`royal`** | 💎 |

**1. Upload the pack once** (needs `aiogram` 3.x). `OWNER_ID` is your Telegram id, and you must have started the bot:

```bash
BOT_TOKEN=123:abc OWNER_ID=111222333 python3 -m emerald_emoji.upload_pack
```

This creates the `emerald_by_<bot>` pack, prints the `t.me/addemoji/...` link and saves
`emerald_emoji/ids.json`. If you run it again later, it only adds the emoji that are new.

**2. Use them in texts.** Messages must be sent with `parse_mode="HTML"`:

```python
from emerald_emoji import e

await message.answer_photo(photo, caption=f"{e('payout')} Введите сумму выплаты\n{e('bolt')} Доступно: {balance} $",
                           parse_mode="HTML")
```

Until `ids.json` exists, `e()` returns the regular emoji, so the texts already work.

Whether animated emoji show up in a bot's messages depends on Telegram's current rules for bots
using custom emoji. If they appear as regular emoji, the bot isn't allowed to send custom emoji yet.
The pack itself always works: anyone with Premium can add it from the link.

**Changing the emoji:** edit `../tools/emoji_build.py` and run `python3 ../tools/emoji_build.py`.
`node ../tools/emoji_preview.js` (needs `npm i lottie-web` and ffmpeg) re-renders the preview.

# Bot avatar

`../avatar.png` (1280×1280) is the profile photo in the card style: the cards' emerald wearing the
emerald crown, with "EMERALD" underneath. Everything sits inside the circle Telegram crops to.
Set it in @BotFather → /mybots → Edit Bot → Edit Botpic. Source: `../avatar.html`; re-render it with
`node ../tools/render_avatar.js`.
