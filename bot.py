import asyncio
import logging
import os
from datetime import date
from zoneinfo import ZoneInfo

import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден! Добавь в .env")

BASE_URL = os.getenv("RENDER_EXTERNAL_HOSTNAME")  # Render сам подставит, или укажи вручную после деплоя
WEBHOOK_PATH = f"/bot/{TOKEN}"
WEBHOOK_URL = f"https://{BASE_URL}{WEBHOOK_PATH}"

logging.basicConfig(level=logging.INFO)

dp = Dispatcher()

DB_FILE = "diet_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                norm_calories REAL DEFAULT 0,
                norm_proteins REAL DEFAULT 0,
                norm_fats REAL DEFAULT 0,
                norm_carbs REAL DEFAULT 0,
                water_norm INTEGER DEFAULT 3000,
                daily_calories REAL DEFAULT 0,
                daily_proteins REAL DEFAULT 0,
                daily_fats REAL DEFAULT 0,
                daily_carbs REAL DEFAULT 0,
                daily_water INTEGER DEFAULT 0,
                last_date TEXT
            )
        """)
        await db.commit()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await init_db()
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT norm_calories FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()

    if row is None or row[0] == 0:
        await message.answer(
            f"Привет, {message.from_user.first_name}! 👋\n"
            "Введи нормы КБЖУ через пробелы: калории белки жиры углеводы\n"
            "Пример: 2500 150 80 250"
        )
    else:
        await message.answer("Ты уже настроен! Пиши еду типа 'гречка 150' или 'вода 500'")

async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)
    print("Webhook установлен:", WEBHOOK_URL)

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    print("Webhook удалён")

def main():
    bot = Bot(token=TOKEN)
    app = web.Application()
    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # Запуск
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

if __name__ == "__main__":
    main()
