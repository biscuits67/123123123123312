"""How to send the Emerald cards with aiogram 3.
Copy the `emerald_cards` folder next to your bot and `pip install pillow`.
Captions stay the same as your current texts."""
from aiogram.types import BufferedInputFile, FSInputFile

from emerald_cards import cards


def photo(data: bytes) -> BufferedInputFile:
    return BufferedInputFile(data, filename="emerald.jpg")


# --- static cards: just a file ---
async def application_accepted(bot, user_id):
    await bot.send_photo(
        user_id,
        FSInputFile(cards.static("application_accepted")),
        caption="✅ Заявка была принята, успешной работы! Если у вас не отобразилось меню бота пропишите /start",
    )


# --- dynamic cards: values are drawn on the image ---
async def application_rejected(bot, user_id, config):
    await bot.send_photo(
        user_id,
        photo(cards.application_rejected(config["admin_username"])),
        caption=f"❌ Заявка была отклонена, для уточнения причины свяжитесь с администрацией - {config['admin_username']}",
    )


async def ask_payout_amount(call, DB):
    balance = DB.get(user_id=call.from_user.id, data="balance", table=DB.users_table)
    await call.message.answer_photo(
        photo(cards.payout_amount(balance)),
        caption=f"💸 Введите сумму выплаты\n⚡️ Доступно: {balance} $",
    )


async def ask_wallet_address(message, wallet_name):
    await message.answer_photo(
        photo(cards.wallet_address(wallet_name)),
        caption=f"💳 Введите новый адрес вашего {wallet_name} кошелька",
    )


async def no_wallet(call):
    wallet = str(call.data).split("_")[1]
    await call.message.answer_photo(
        photo(cards.payout_no_wallet(wallet)),
        caption=f"❌ Укажите {wallet} кошелек для выплаты",
    )


async def branch(message, branch, owner_name, owner_username, owner_id, members_count, turnover):
    await message.answer_photo(
        photo(cards.branch_info(members_count, turnover, branch["percentage"])),
        caption=(
            f"👑 Owner:\n• {owner_name} (@{owner_username})\n• ID: <code>{owner_id}</code>\n\n"
            f"👥 Участников: {members_count}\n💰 Оборот филиала: {round(turnover, 2)} $\n\n"
            f"📊 Процент филиала: {branch['percentage']}%"
        ),
        parse_mode="HTML",
    )


# --- menu sections: a card + your inline keyboard in one message ---
async def menu_materials(msg, materials_btns):
    await msg.answer_photo(FSInputFile(cards.static("menu_materials")), reply_markup=materials_btns)


async def menu_info(msg, kb):
    await msg.answer_photo(FSInputFile(cards.static("menu_info")), reply_markup=kb)


async def menu_domains(msg, active_domains, keyboard):
    if not active_domains:
        await msg.answer_photo(FSInputFile(cards.static("domains_not_found")),
                               caption="❌ Активные домены не найдены")
        return
    text = "🔗 <b>Актуальные домены</b>\n\n" + "".join(f"• <code>{d}</code>\n" for d in active_domains)
    await msg.answer_photo(
        photo(cards.domains_list(active_domains, all_active=True)),
        caption=text, parse_mode="HTML", reply_markup=keyboard,
    )


async def admin_domains(msg, domains, active_domain, text):
    # text = your existing "🔗 <b>Актуальные домены</b>..." string
    await msg.answer_photo(photo(cards.domains_list(domains, active_domain)), caption=text, parse_mode="HTML")


async def domain_added(msg, domain):
    await msg.answer_photo(photo(cards.domain_added(domain)), caption=f"✅ Домен {domain} добавлен!")


# Note: a text message ("Загрузка...") can't be edited into a photo.
# Delete it and send the photo instead:  await msg2edit.delete(); await msg.answer_photo(...)


# --- top deposits ---
async def top_deposits_menu(msg, top_deposits_btns):
    await msg.delete()
    await msg.answer_photo(FSInputFile(cards.static("top_deposits")),
                           caption="🥇 Выберите период для топа депозитов:", reply_markup=top_deposits_btns)


async def top_deposits(call, rows):
    # call.data = "top_deposits_day" | "_week" | "_month" | "_all"
    # rows = [(name, amount), ...] from your DB, best first (5 are drawn, caption can hold all)
    await call.message.answer_photo(photo(cards.top_deposits(call.data, rows)))


# --- access checks ---
async def banned(msg):
    await msg.answer_photo(FSInputFile(cards.static("banned")),
                           caption="⛔️ Вы были заблокированы администрацией")
