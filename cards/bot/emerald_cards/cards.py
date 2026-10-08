"""One function per bot message. Each returns ready-to-send image bytes
(dynamic cards) or a path to a PNG (static cards)."""
from pathlib import Path

from .render import ASSETS, render

STATIC = (
    "application_accepted",  # ✅ Заявка была принята
    "wallet_trx",            # 💳 Выберите кошелек TRX
    "nickname",              # ⭐️ Введите новый ник
    "payout_choose",         # 💸 На какой кошелек вы хотите заказать выплату?
    "payout_done",           # ✅ Выплата совершена
    "payout_rejected",       # ❌ Выплата отклонена
    "forum_link",            # 👍 Отлично, теперь отправьте ссылку на свой профиль форума
    "application_sent",      # ✈️ Ваша заявка успешно отправлена!
    "application_failed",    # ⛔️ Ваша заявка не была отправлена!
    "enter_number",          # ❌ Введите число
    "promo_name",            # 💬 Введите название промокода
    "promo_exists",          # ❌ Данный промокод уже существует
    "domain_bad_format",     # ❌ Неверный формат домена. Пример: example.com
    "domains_not_found",     # ❌ Активные домены не найдены
    "menu_materials",        # 📕 Материалы
    "menu_info",             # ℹ️ Информация
    "top_deposits",          # 🥇 Выберите период для топа депозитов
    "add_domain",            # 💬 Введите домен (example.com)
    "cancelled",             # Операция отменена.
    "confirmed",             # Операция подтверждена.
    "unknown_command",       # Неизвестная команда
    "banned",                # ⛔️ Вы были заблокированы администрацией
    "profile_error",         # ⛔️ Ошибка профиля. Обратитесь к администратору.
)


def static(name: str) -> Path:
    if name not in STATIC:
        raise ValueError(f"unknown static card {name!r}, choose from {STATIC}")
    return ASSETS / "static" / f"{name}.jpg"


def money(value) -> str:
    """1234.5 -> '1 234.50 $' (thin, non-breaking thousands separator)."""
    try:
        return f"{float(value):,.2f}".replace(",", " ") + " $"
    except (TypeError, ValueError):
        return f"{value} $"


def _at(username) -> str:
    username = str(username or "").strip()
    return username if not username or username.startswith("@") else "@" + username


def application_rejected(admin_username) -> bytes:
    """❌ Заявка была отклонена ... свяжитесь с администрацией - {admin_username}"""
    return render("application_rejected", admin=_at(admin_username))


def wallet_address(wallet_name) -> bytes:
    """💳 Введите новый адрес вашего {wallet_name} кошелька"""
    return render("wallet_address", wallet=wallet_name)


def payout_no_wallet(wallet_name) -> bytes:
    """❌ Укажите {wallet} кошелек для выплаты"""
    return render("payout_no_wallet", wallet=wallet_name)


def payout_amount(balance) -> bytes:
    """💸 Введите сумму выплаты ⚡️ Доступно: {balance} $"""
    return render("payout_amount", balance=money(balance))


def branch_info(members, turnover, percent) -> bytes:
    """👥 Участников / 💰 Оборот филиала / 📊 Процент филиала"""
    return render(
        "branch_info",
        members=members,
        turnover=money(round(float(turnover), 2)),
        percent=f"{percent}%",
    )


def nickname_saved(nick) -> bytes:
    """✅ Новый ник успешно сохранен!"""
    return render("nickname_saved", nick=nick)


def domain_added(domain) -> bytes:
    """✅ Домен {domain} добавлен!"""
    return render("domain_added", domain=domain)


def domain_exists(domain) -> bytes:
    """❌ Домен {domain} уже существует!"""
    return render("domain_exists", domain=domain)


def domains_list(domains, active_domain=None, all_active=False) -> bytes:
    """🔗 Актуальные домены.
    Admin list: domains_list(domains, active_domain) — the active one is highlighted.
    User menu:  domains_list(active_domains, all_active=True) — every domain gets a check."""
    return render("domains_list", domains=(list(domains or []), active_domain, all_active))


TOP_PERIODS = {"day": "top_day", "week": "top_week", "month": "top_month", "all": "top_all"}


def top_deposits(period, rows) -> bytes:
    """📅 Топ депозитов за день / неделю / месяц / всё время.
    period -- "day" | "week" | "month" | "all" (or callback_data like "top_deposits_week")
    rows   -- [(name, amount), ...] best first; up to 5 are shown, amounts as numbers or text."""
    period = str(period).rsplit("_", 1)[-1]
    if period not in TOP_PERIODS:
        raise ValueError(f"period must be one of {list(TOP_PERIODS)}")
    prepared = [(name, money(amount) if isinstance(amount, (int, float)) else amount) for name, amount in rows]
    return render(TOP_PERIODS[period], rows=prepared)
