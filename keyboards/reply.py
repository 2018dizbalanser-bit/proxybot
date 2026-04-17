from aiogram import types
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from utils.i18n import t


def main_keyboard(lang: str = 'ru'):
    builder = ReplyKeyboardBuilder()
    builder.button(text=t('btn_get_proxy', lang))
    builder.button(text=t('btn_cabinet', lang))
    builder.adjust(1, 1)
    return builder.as_markup(resize_keyboard=True)


def proxy_keyboard(lang: str = 'ru'):
    builder = ReplyKeyboardBuilder()
    builder.button(text=t('btn_other_proxy', lang))
    builder.button(text=t('btn_main_menu', lang))
    builder.adjust(1, 1)
    return builder.as_markup(resize_keyboard=True)
