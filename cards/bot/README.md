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
| `cards.new_deposit(worker, amount)` | 🚀 Новый депозит · Воркер · Сумма USD | drawn: worker, amount |

Static cards are JPEG files. Dynamic functions return JPEG bytes (~80 ms per card) — send them with
`BufferedInputFile(data, "emerald.jpg")`. See `example_aiogram.py`.

The domains list shows up to 5 rows; the rest becomes «+ ещё N» (the active domain is always shown).
Long values shrink to fit and are cut with `…` if needed; emoji in names are removed
(the brand font has no emoji glyphs).

## Changing the design
Everything is drawn from `../card.html`. After editing it run `node ../tools/render.js`
(needs Playwright), then `python3 ../tools/pack.py` — they re-render the preview PNGs, the static cards and the
backgrounds + `layout.json` used by the Python code.
