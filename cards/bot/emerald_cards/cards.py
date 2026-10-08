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
)


def static(name: str) -> Path:
    if name not in STATIC:
        raise ValueError(f"unknown static card {name!r}, choose from {STATIC}")
    return ASSETS / "static" / f"{name}.png"


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
