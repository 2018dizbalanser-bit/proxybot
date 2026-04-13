from aiogram import types
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def main_keyboard():
    builder = ReplyKeyboardBuilder()

    # Твоя текущая кнопка (возможно она называется иначе, оставь свою)
    builder.button(text="🚀 Получить прокси")

    # НОВАЯ КНОПКА
    builder.button(text="👤 Личный кабинет")

    builder.adjust(1, 1)  # По одной кнопке в ряд
    return builder.as_markup(resize_keyboard=True)


def proxy_actions_kb():
    builder = ReplyKeyboardBuilder()

    builder.row(
        types.KeyboardButton(text="🔄 Другой прокси")
    )
    builder.row(
        types.KeyboardButton(text="🔝 Главное меню")
    )

    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Выберите действие:"
    )
