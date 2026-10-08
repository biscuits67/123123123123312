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
| `cards.static("forum_link")` | 👍 Отправьте ссылку на профиль форума | PNG file |
| `cards.static("application_sent")` | ✈️ Ваша заявка успешно отправлена | PNG file |
| `cards.static("application_failed")` | ⛔️ Ваша заявка не была отправлена | PNG file |
| `cards.nickname_saved(nick)` | ✅ Новый ник успешно сохранен | drawn: nick |
| `cards.static("enter_number")` | ❌ Введите число | PNG file |
| `cards.static("promo_name")` | 💬 Введите название промокода | PNG file |
| `cards.static("promo_exists")` | ❌ Данный промокод уже существует | PNG file |
| `cards.static("domain_bad_format")` | ❌ Неверный формат домена | PNG file |
| `cards.domain_added(domain)` | ✅ Домен {domain} добавлен | drawn: domain |
| `cards.domain_exists(domain)` | ❌ Домен {domain} уже существует | drawn: domain |
| `cards.domains_list(domains, active_domain)` | 🔗 Актуальные домены (admin, active highlighted) | drawn: list |
| `cards.domains_list(active_domains, all_active=True)` | 🔗 Актуальные домены (menu) | drawn: list |
| `cards.static("domains_not_found")` | ❌ Активные домены не найдены | PNG file |
| `cards.static("menu_materials")` | 📕 Материалы | PNG file |
| `cards.static("menu_info")` | ℹ️ Информация | PNG file |

Dynamic functions return JPEG bytes (~80 ms per card) — send them with
`BufferedInputFile(data, "emerald.jpg")`. See `example_aiogram.py`.

The domains list shows up to 5 rows; the rest becomes «+ ещё N» (the active domain is always shown).
Long values shrink to fit and are cut with `…` if needed; emoji in names are removed
(the brand font has no emoji glyphs).

## Changing the design
Everything is drawn from `../card.html`. After editing it run `node ../tools/render.js`
(needs Playwright) — it re-renders the preview PNGs, the static cards and the
backgrounds + `layout.json` used by the Python code.
