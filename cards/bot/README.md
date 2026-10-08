# Emerald cards for the bot

`emerald_cards/` is a self-contained folder: copy it next to your bot and `pip install pillow`.

| Function | Message | Type |
|---|---|---|
| `cards.static("application_accepted")` | ✅ Заявка была принята | PNG file |
| `cards.application_rejected(admin_username)` | ❌ Заявка была отклонена | drawn: admin |
| `cards.static("wallet_trx")` | 💳 Выберите кошелек TRX | PNG file |
| `cards.static("nickname")` | ⭐️ Введите новый ник | PNG file |
| `cards.wallet_address(wallet_name)` | 💳 Введите новый адрес {wallet_name} кошелька | drawn: wallet |
| `cards.static("payout_choose")` | 💸 На какой кошелек заказать выплату? | PNG file |
| `cards.static("payout_done")` | ✅ Выплата совершена | PNG file |
| `cards.static("payout_rejected")` | ❌ Выплата отклонена | PNG file |
| `cards.payout_no_wallet(wallet)` | ❌ Укажите {wallet} кошелек для выплаты | drawn: wallet |
| `cards.payout_amount(balance)` | 💸 Введите сумму выплаты ⚡️ Доступно | drawn: balance |
| `cards.branch_info(members, turnover, percent)` | 👥 Участников / 💰 Оборот / 📊 Процент | drawn: stats |

Dynamic functions return JPEG bytes (~80 ms per card) — send them with
`BufferedInputFile(data, "emerald.jpg")`. See `example_aiogram.py`.

Long values shrink to fit and are cut with `…` if needed; emoji in names are removed
(the brand font has no emoji glyphs).

## Changing the design
Everything is drawn from `../card.html`. After editing it run `node ../tools/render.js`
(needs Playwright) — it re-renders the preview PNGs, the static cards and the
backgrounds + `layout.json` used by the Python code.
