from aiogram import Router, types
from aiogram.filters import CommandStart

from database.requests.add import add_user
from keyboards.reply import main_keyboard

router = Router()

@router.message(CommandStart())
async def start_command(message: types.Message):
    # Добавляем или обновляем пользователя в БД
    await add_user(
        tg_id=message.from_user.id,
        username=message.from_user.username
    )

    # Адаптированный текст в стиле твоего примера
    text = (
        f"<b>Привет, {message.from_user.first_name}!</b> 👋\n\n"
        f"Я бот для раздачи <b>бесплатных и скоростных</b> прокси для Telegram.\n"
        f"С моей помощью твой мессенджер будет летать даже при сбоях сети. 🚀\n\n"
        f"🔐 <b>Что я умею:</b>\n"
        f"1️⃣ Выдаю только актуальные и проверенные прокси.\n"
        f"2️⃣ Автоматически подбираю самый быстрый сервер под твой регион.\n"
        f"3️⃣ Если прокси станет нестабильным — я мгновенно предложу замену.\n\n"
        f"👇 <b>Нажми на кнопку ниже</b>, чтобы получить свой первый доступ прямо сейчас!"
    )

    await message.answer(
        text,
        reply_markup=main_keyboard()
    )