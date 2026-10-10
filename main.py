"""Точка входа BarberFlow. Запуск: python main.py (Windows: см. README.md)."""
from __future__ import annotations

import logging

from telegram.ext import Application, CallbackQueryHandler, CommandHandler

from bot.handlers import on_callback, start
from config import BOT_TOKEN
from database.db import init_db
from database.seed import seed

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("barberflow")


def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN == "PASTE_YOUR_TOKEN_HERE":
        raise SystemExit(
            "BOT_TOKEN не задан. Скопируйте .env.example в .env "
            "и вставьте токен от @BotFather. Подробности — в README.md."
        )

    init_db()
    stats = seed()
    logger.info("DB seed: %s", stats)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_callback))

    logger.info("BarberFlow запущен (polling).")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
