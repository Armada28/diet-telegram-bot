import asyncio
import aiosqlite
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Токен берём из переменных окружения (Railway → Variables)
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    print("Ошибка: переменная BOT_TOKEN не найдена в окружении!")
    exit(1)

DB_NAME = "bju_bot.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ─── СОСТОЯНИЯ (FSM) ───
class Reg(StatesGroup):
    name = State()
    goal = State()

class Food(StatesGroup):
    waiting_for_calories = State()

# ─── ГЛАВНАЯ КЛАВИАТУРА ───
def main_kb():
    kb = [
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🍎 Быстрый перекус")],
        [KeyboardButton(text="♻️ Сброс дня")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=False)

# ─── ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ───
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                goal REAL,
                eaten REAL DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS products (
                product_name TEXT PRIMARY KEY,
                kcal REAL
            )
        ''')
        await db.commit()

# ─── ОБРАБОТЧИКИ ───
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT name FROM users WHERE id = ?", (message.from_user.id,)) as cursor:
            user = await cursor.fetchone()
            if user:
                await message.answer(f"С возвращением, {user[0]}!", reply_markup=main_kb())
                return

    await message.answer("Привет! Давай зарегистрируемся. Как тебя зовут?")
    await state.set_state(Reg.name)

@dp.message(Reg.name)
async def reg_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Какая твоя дневная норма калорий? (например: 2200 или 1850.5)")
    await state.set_state(Reg.goal)

@dp.message(Reg.goal)
async def reg_goal(message: types.Message, state: FSMContext):
    try:
        goal_text = message.text.replace(',', '.').strip()
        goal = float(goal_text)
        if goal <= 0:
            raise ValueError("Норма калорий должна быть больше 0")

        data = await state.get_data()
        name = data.get('name', 'Пользователь')

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT OR REPLACE INTO users (id, name, goal, eaten) VALUES (?, ?, ?, 0)",
                (message.from_user.id, name, goal)
            )
            await db.commit()

        await message.answer(
            f"Отлично, {name}! Цель {goal} ккал установлена.\n"
            f"Теперь можешь пользоваться ботом 👌",
            reply_markup=main_kb()
        )
        await state.clear()

    except ValueError:
        await message.answer("Пожалуйста, введи число (можно с точкой или запятой).\nПример: 2100")

# ─── ЗАПУСК БОТА (polling) ───
async def main():
    print("Бот запускается...")
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
