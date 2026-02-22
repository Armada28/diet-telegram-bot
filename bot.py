import asyncio
import aiosqlite
import os
import signal
import sys
import logging

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Настройка логгинга для отладки
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен берём из переменных окружения
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    logger.error("Переменная BOT_TOKEN не найдена в окружении!")
    sys.exit(1)

DB_NAME = "bju_bot.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ─── СОСТОЯНИЯ (FSM) ───
class Reg(StatesGroup):
    name = State()
    goal = State()

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

# ─── ДОБАВЛЕНИЕ ДЕФОЛТНЫХ ПРОДУКТОВ (один раз при запуске) ───
async def add_default_products():
    products = [
        ("гречка", 313.0),   # сухая ~313 ккал/100г
        ("капуста", 25.0),   # свежая ~25 ккал/100г
        ("рис", 344.0),      # сухой белый ~344 ккал/100г
        ("овсянка", 366.0),  # сухие хлопья ~366 ккал/100г
        ("макароны", 371.0), # сухие ~371 ккал/100г
        ("картофель", 77.0), # варёный ~77 ккал/100г
        ("курица", 165.0),   # грудка варёная ~165 ккал/100г
        ("яйцо", 155.0),     # куриное варёное ~155 ккал/100г
        ("творог", 71.0),    # обезжиренный ~71 ккал/100г
        ("банан", 89.0),     # свежий ~89 ккал/100г
        # Добавь больше продуктов здесь по желанию
    ]

    async with aiosqlite.connect(DB_NAME) as db:
        for name, kcal in products:
            await db.execute(
                "INSERT OR IGNORE INTO products (product_name, kcal) VALUES (?, ?)",
                (name.lower(), kcal)
            )
        await db.commit()
    logger.info("Добавлены дефолтные продукты в базу")

# ─── ОБРАБОТЧИКИ ───
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT name FROM users WHERE id = ?", (message.from_user.id,)) as cursor:
                user = await cursor.fetchone()
                if user:
                    await message.answer(f"С возвращением, {user[0]}!", reply_markup=main_kb())
                    return
        await message.answer("Привет! Давай зарегистрируемся. Как тебя зовут?")
        await state.set_state(Reg.name)
    except Exception as e:
        logger.error(f"Ошибка в /start: {e}")
        await message.answer("Произошла ошибка. Попробуй позже.")

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
    except Exception as e:
        logger.error(f"Ошибка в reg_goal: {e}")
        await message.answer("Ошибка при регистрации. Попробуй заново.")

# ─── ОБЩИЙ ОБРАБОТЧИК ДЛЯ ВВОДА ЕДЫ ───
@dp.message(F.text)
async def handle_food_input(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return  # Пропускаем, если в состоянии

    text = message.text.lower().strip()
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        await message.reply("Формат: продукт количество\nПример: гречка 100")
        return

    product = parts[0]
    try:
        amount = float(parts[1])
    except ValueError:
        await message.reply("Количество должно быть числом")
        return

    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                "SELECT kcal FROM products WHERE product_name = ?", (product,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    kcal_per_100 = row[0]
                    total_kcal = (kcal_per_100 / 100) * amount

                    # Проверяем наличие пользователя
                    async with db.execute("SELECT id FROM users WHERE id = ?", (message.from_user.id,)) as cursor:
                        user_exists = await cursor.fetchone()
                        if not user_exists:
                            await message.reply("Сначала зарегистрируйся через /start")
                            return

                    await db.execute(
                        "UPDATE users SET eaten = eaten + ? WHERE id = ?",
                        (total_kcal, message.from_user.id)
                    )
                    await db.commit()

                    await message.reply(f"Добавлено {total_kcal:.1f} ккал от {product} ({amount} г)")
                else:
                    await message.reply(f"Продукт '{product}' не найден в базе. Добавь через /addproduct продукт ккал")
    except Exception as e:
        logger.error(f"Ошибка в handle_food_input: {e}")
        await message.reply("Ошибка при добавлении. Попробуй позже.")

# ─── ОБРАБОТЧИК СТАТИСТИКИ ───
@dp.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT goal, eaten FROM users WHERE id = ?", (message.from_user.id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    goal, eaten = row
                    left = goal - eaten if goal > eaten else 0
                    await message.answer(f"Цель: {goal} ккал\nСъедено: {eaten:.1f} ккал\nОсталось: {left:.1f} ккал")
                else:
                    await message.answer("Сначала зарегистрируйся через /start")
    except Exception as e:
        logger.error(f"Ошибка в show_stats: {e}")
        await message.answer("Ошибка при получении статистики.")

# ─── ОБРАБОТЧИК СБРОСА ДНЯ ───
@dp.message(F.text == "♻️ Сброс дня")
async def reset_day(message: types.Message):
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE users SET eaten = 0 WHERE id = ?", (message.from_user.id,))
            await db.commit()
        await message.answer("День сброшен! Eaten = 0")
    except Exception as e:
        logger.error(f"Ошибка в reset_day: {e}")
        await message.answer("Ошибка при сбросе.")

# ─── КОМАНДА ДЛЯ ДОБАВЛЕНИЯ ПРОДУКТА (для админа или всех) ───
@dp.message(Command("addproduct"))
async def add_product(message: types.Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.reply("Формат: /addproduct продукт ккал\nПример: /addproduct яблоко 52")
        return

    product = parts[1].lower()
    try:
        kcal = float(parts[2])
    except ValueError:
        await message.reply("Калории должны быть числом")
        return

    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT OR REPLACE INTO products (product_name, kcal) VALUES (?, ?)",
                (product, kcal)
            )
            await db.commit()
        await message.reply(f"Продукт '{product}' добавлен с {kcal} ккал/100г")
    except Exception as e:
        logger.error(f"Ошибка в add_product: {e}")
        await message.reply("Ошибка при добавлении продукта.")

# ─── GRACEFUL SHUTDOWN ───
async def shutdown():
    logger.info("Получен SIGTERM, graceful shutdown...")
    await bot.session.close()
    sys.exit(0)

def handle_sigterm(signum, frame):
    asyncio.create_task(shutdown())

signal.signal(signal.SIGTERM, handle_sigterm)

# ─── ЗАПУСК ───
async def main():
    logger.info("Бот запускается...")
    await init_db()
    await add_default_products()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
