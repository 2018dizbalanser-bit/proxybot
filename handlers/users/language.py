from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.requests.update import update_user_language
from keyboards.reply import main_keyboard
from utils.i18n import t

router = Router()

LANGUAGES = [
    ('ru', '🇷🇺 Русский'),
    ('en', '🇬🇧 English'),
    ('fa', '🇮🇷 فارسی'),
    ('tr', '🇹🇷 Türkçe'),
    ('ar', '🇸🇦 العربية'),
    ('kk', '🇰🇿 Қазақша'),
    ('uz', '🇺🇿 O\'zbek'),
    ('ur', '🇵🇰 اردو'),
    ('hi', '🇮🇳 हिन्दी'),
    ('id', '🇮🇩 Indonesia'),
]


def get_language_keyboard():
    builder = InlineKeyboardBuilder()
    for code, label in LANGUAGES:
        builder.button(text=label, callback_data=f"set_lang_{code}")
    builder.adjust(2)
    return builder.as_markup()


@router.message(Command("language"))
async def language_command(message: types.Message, lang: str):
    await message.answer(
        t('language_choose', lang),
        reply_markup=get_language_keyboard()
    )


@router.callback_query(F.data == "open_language")
async def open_language_handler(callback: types.CallbackQuery, lang: str):
    await callback.message.edit_text(
        t('language_choose', lang),
        reply_markup=get_language_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_lang_"))
async def set_language_handler(callback: types.CallbackQuery):
    lang_code = callback.data.split("set_lang_")[1]
    valid = [code for code, _ in LANGUAGES]
    if lang_code not in valid:
        await callback.answer()
        return

    await update_user_language(callback.from_user.id, lang_code)
    await callback.answer()
    await callback.message.answer(t('language_set', lang_code), reply_markup=main_keyboard(lang_code))
