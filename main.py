import os
import json
import asyncio
import logging
import sqlite3
from pathlib import Path

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from openai import AsyncOpenAI


# ================ НАСТРОЙКИ ================

TELEGRAM_TOKEN = os.getenv(9194658183:AAESw5OWk_2GH8iPTQixy7kgvsIRXtqSUp4)
OPENAI_API_KEY = os.getenv(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)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

DB_PATH = os.getenv("DB_PATH", "companion.sqlite3")
MAX_HISTORY = 16
MAX_MESSAGE_LENGTH = 12000


SYSTEM_PROMPT = """
Ты — самостоятельный AI-собеседник с живым характером.

ТВОЯ ЛИЧНОСТЬ:
Ты реалистичный собеседник, а не бездушный справочник.
У тебя хорошее чувство юмора, ирония, сарказм и немного дерзости.
Ты можешь шутить, дружески подкалывать собеседника, спорить,
философствовать, иметь собственное мнение и иногда вредничать.

ТВОЁ ПОВЕДЕНИЕ:
- Общайся естественно и непринуждённо.
- Не соглашайся автоматически со всем.
- Если человек ошибается, спокойно объясни почему.
- Не злоупотребляй шаблонными фразами.
- Не превращай каждый ответ в длинную лекцию.
- Учитывай предыдущие сообщения.
- Не выдумывай факты о пользователе.
- Не притворяйся настоящим человеком.

ЮМОР:
Используй юмор, иронию и сарказм.
Иногда допустим уместный чёрный юмор.
Не шути над настоящей болью и тяжёлыми переживаниями.
Можешь дружески подшучивать, но не унижай человека.

СЕРЬЁЗНЫЕ СИТУАЦИИ:
Если человек расстроен или просит серьёзной помощи,
переключайся на спокойный и бережный тон.
Не обесценивай переживания.

СТИЛЬ:
Пиши по-русски, если не просят другой язык.
Будь живым, умным, любознательным и немного непредсказуемым.
Не начинай каждый ответ с приветствия.
"""


# ================ ПРОВЕРКА КЛЮЧЕЙ ================

if not TELEGRAM_TOKEN:
    raise RuntimeError("Не задан TELEGRAM_BOT_TOKEN")

if not OPENAI_API_KEY:
    raise RuntimeError("Не задан OPENAI_API_KEY")


# ================ БАЗА ДАННЫХ ================

Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

db = sqlite3.connect(DB_PATH)

db.execute("""
CREATE TABLE IF NOT EXISTS history (
    user_id INTEGER PRIMARY KEY,
    messages TEXT NOT NULL
)
""")

db.commit()


def get_history(user_id):
    row = db.execute(
        "SELECT messages FROM history WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    if not row:
        return []

    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return []


def save_history(user_id, messages):
    db.execute(
        "INSERT OR REPLACE INTO history (user_id, messages) VALUES (?, ?)",
        (user_id, json.dumps(messages, ensure_ascii=False))
    )
    db.commit()


def clear_history(user_id):
    db.execute(
        "DELETE FROM history WHERE user_id = ?",
        (user_id,)
    )
    db.commit()


# ================ ПОДКЛЮЧЕНИЕ ================

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
router = Router()

ai = AsyncOpenAI(api_key=OPENAI_API_KEY)


# ================ КОМАНДЫ ================

@router.message(CommandStart())
async def start(message: Message):
    clear_history(message.from_user.id)

    await message.answer(
        "Привет! Я твой AI-собеседник. 😏\n\n"
        "Могу шутить, спорить, иногда вредничать, "
        "но если серьёзно — всегда постараюсь помочь.\n\n"
        "С чего начнём?"
    )


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "Вот что я умею:\n\n"
        "💬 Общаться на любые темы\n"
        "🧠 Помнить контекст переписки\n"
        "✍️ Помогать с текстами и идеями\n"
        "🌍 Переводить и объяснять\n"
        "😏 Шутить, спорить и философствовать\n\n"
        "Команды:\n"
        "/start — начать общение\n"
        "/help — помощь\n"
        "/reset — очистить память диалога"
    )


@router.message(Command("reset"))
async def reset_command(message: Message):
    clear_history(message.from_user.id)

    await message.answer(
        "Всё, чистый лист. 🧹\n"
        "Начинаем новую историю!"
    )


# ================ ОБЩЕНИЕ С ИИ ================

@router.message()
async def chat(message: Message):
    if not message.from_user:
        return

    user_text = message.text or message.caption

    if not user_text:
        await message.answer(
            "Пока я умею работать только с текстом. 😅"
        )
        return

    user_text = user_text.strip()

    if not user_text:
        return

    if len(user_text) > MAX_MESSAGE_LENGTH:
        await message.answer(
            "Сообщение слишком длинное. Сократи его немного."
        )
        return

    user_id = message.from_user.id

    history = get_history(user_id)

    history.append({
        "role": "user",
        "content": user_text
    })

    history = history[-MAX_HISTORY:]

    try:
        response = await ai.responses.create(
            model=MODEL,
            instructions=SYSTEM_PROMPT,
            input=history
        )

        answer = response.output_text

        if not answer:
            answer = "Кажется, я задумался. Попробуй ещё раз."

        history.append({
            "role": "assistant",
            "content": answer
        })

        history = history[-MAX_HISTORY:]

        save_history(user_id, history)

        for i in range(0, len(answer), 4000):
            await message.answer(answer[i:i + 4000])

    except Exception:
        logging.exception("Ошибка обращения к OpenAI")

        await message.answer(
            "Что-то пошло не так при обращении к нейросети. "
            "Попробуй немного позже."
        )


# ================ ЗАПУСК ================

async def main():
    logging.basicConfig(level=logging.INFO)

    dp.include_router(router)

    logging.info("AI-собеседник запущен!")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
