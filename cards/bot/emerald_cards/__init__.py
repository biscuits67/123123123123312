"""Emerald (EMRLD) — graphic cards for the Telegram bot.

Static cards are ready-made PNGs; dynamic cards are drawn on the fly
(balance, wallet, admin, branch stats) on top of pre-rendered backgrounds.

    from emerald_cards import cards
    photo = cards.payout_amount(balance)            # -> bytes (JPEG)
    path  = cards.static("application_accepted")    # -> path to PNG
"""
from . import cards
from .render import render

__all__ = ["cards", "render"]
