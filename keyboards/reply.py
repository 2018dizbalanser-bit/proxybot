from aiogram import types
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def main_keyboard():
    builder = ReplyKeyboardBuilder()

    builder.row(
        types.KeyboardButton(text="🚀 Получить прокси")
    )

    # Можно добавить еще кнопки, например, "Профиль" или "Поддержка"
    # builder.row(types.KeyboardButton(text="Мой профиль 👤"))

    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Выберите действие:"
    )