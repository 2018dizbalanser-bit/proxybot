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