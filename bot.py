import asyncio
import aiosqlite
import os
import sys
import time
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Бот будет брать токен из переменных окружения
TOKEN = os.getenv("BOT_TOKEN")
DB_NAME = "bju_bot.db"

dp = Dispatcher()

# --- СОСТОЯНИЯ (FSM) ---
class Reg(StatesGroup):
    name = State()
    goal = State()

class Food(StatesGroup):
    waiting_for_calories = State()

# --- КЛАВИАТУРА ---
def main_kb():
    kb = [
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🍎 Быстрый перекус")],
        [KeyboardButton(text="♻️ Сброс дня")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users
            (id INTEGER PRIMARY KEY, name TEXT, goal REAL, eaten REAL DEFAULT 0)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS products
            (product_name TEXT PRIMARY KEY, kcal REAL)''')
        await db.commit()

# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT name FROM users WHERE id = ?", (message.from_user.id,)) as c:
            user = await c.fetchone()
            if user:
                return await message.answer(f"С возвращением, {user[0]}!", reply_markup=main_kb())
    
    await message.answer("Привет! Давай зарегистрируемся. Как тебя зовут?")
    await state.set_state(Reg.name)

@dp.message(Reg.name)
async def reg_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Какая твоя дневная норма калорий?")
    await state.set_state(Reg.goal)

@dp.message(Reg.goal)
async def reg_goal(message: types.Message, state: FSMContext):
    try:
        goal = float(message.text.replace(',', '.'))
        data = await state.get_data()
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT OR REPLACE INTO users (id, name, goal) VALUES (?, ?, ?)",
                             (message.from_user.id, data['name'], goal))
            await db.commit()
        await message.answer(f"Отлично, {data['name']}! Цель {goal} ккал установлена.", reply_markup=main_kb())
        await state.clear()
    except ValueError:
        awaitPORT", 8080)))

if __name__ == "__main__":
    main()
