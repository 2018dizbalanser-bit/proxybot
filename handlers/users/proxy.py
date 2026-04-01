import asyncio

from aiogram import Router, F, types, Bot

from database.requests.add import add_or_update_vote
from database.requests.get import get_all_channels, get_best_proxy, get_proxy_by_id
from keyboards.inline import get_subscription_keyboard, get_proxy_control_keyboard, get_proxy_vote_keyboard
from utils.ping import parse_proxy_url
from utils.subscription import get_unsubscribed_channels
from utils.texts import get_public_proxy_text, get_proxy_card_text

router = Router()


@router.message(F.text == "🚀 Получить прокси")
async def get_proxy_handler(message: types.Message, bot: Bot):
    channels = await get_all_channels()

    # Получаем ТОЛЬКО те каналы, где юзера еще нет
    unsubscribed = await get_unsubscribed_channels(bot, message.from_user.id, channels)

    if unsubscribed:
        await message.answer(
            "⚠️ <b>Для получения прокси необходимо подписаться на наших спонсоров:</b>\n\n"
            "После подписки нажмите кнопку <i>«Проверить подписку»</i>.",
            # Передаем в клавиатуру только недостающие каналы!
            reply_markup=get_subscription_keyboard(unsubscribed)
        )
    else:
        # Подписан на все (или обязательных каналов вообще нет)
        await send_best_proxy(message, bot=bot)


@router.callback_query(F.data == "check_subscription")
async def check_sub_handler(callback: types.CallbackQuery, bot: Bot):
    channels = await get_all_channels()
    unsubscribed = await get_unsubscribed_channels(bot, callback.from_user.id, channels)

    if not unsubscribed:  # Список пуст, значит подписан на все!
        await callback.answer("✅ Подписка подтверждена!", show_alert=False)
        await send_best_proxy(callback.message, bot=bot, edit_message=True)
    else:
        await callback.answer("❌ Вы подписались не на все каналы!", show_alert=True)
        # КИЛЛЕР-ФИЧА: Обновляем клавиатуру!
        # Если юзер подписался на 1 из 2 каналов, кнопка подписанного канала исчезнет.
        await callback.message.edit_reply_markup(
            reply_markup=get_subscription_keyboard(unsubscribed)
        )


# --- Выдача лучшего прокси ---
async def send_best_proxy(message: types.Message, bot: Bot, edit_message: bool = False, exclude_id: int = None):
    proxy = await get_best_proxy(exclude_id)

    if not proxy:
        text = "😔 <b>К сожалению, сейчас нет доступных рабочих прокси.</b>\nЗагляните немного позже!"
        markup = None
    else:
        bot_info = await bot.get_me()
        # Вызываем нашу ОДНУ функцию для текста
        text = get_public_proxy_text(proxy, bot_info.username)
        markup = get_proxy_vote_keyboard(proxy.id, proxy.url, proxy.likes, proxy.dislikes)

    if edit_message:
        await message.answer(text, reply_markup=markup, disable_web_page_preview=True)
    else:
        await message.answer(text, reply_markup=markup, disable_web_page_preview=True)


@router.callback_query(F.data.startswith("replace_proxy_"))
async def replace_proxy_handler(callback: types.CallbackQuery, bot: Bot):
    # Достаем ID прокси, который сейчас видит юзер
    current_proxy_id = int(callback.data.split("_")[2])

    try:
        await callback.message.delete()
        emoji = await callback.message.answer(
            f"<tg-emoji emoji-id='5388953246486269495'>👍</tg-emoji>"
        )
        await asyncio.sleep(0.6)
        await emoji.delete()
    except Exception:
        pass

    # Вызываем финальную выдачу, как и раньше
    await send_best_proxy(callback.message, bot=bot, edit_message=True, exclude_id=current_proxy_id)


# --- Выдача конкретного прокси (по реф-ссылке) ---
# Добавили bot: Bot в аргументы!
async def send_specific_proxy(message: types.Message, proxy_id: int, bot: Bot):
    proxy = await get_proxy_by_id(proxy_id)

    if not proxy or not proxy.is_active:
        await message.answer(
            "😔 <b>Этот прокси больше недоступен или был удален.</b>\nВоспользуйтесь кнопкой в меню, чтобы получить другой.")
        return

    bot_info = await bot.get_me()

    # Текст без призыва жать "Другой прокси"
    text = get_proxy_card_text(proxy, bot_info.username, is_direct_link=True)

    # Клавиатура без кнопки "Другой прокси"
    markup = get_proxy_vote_keyboard(proxy.id, proxy.url, proxy.likes, proxy.dislikes, show_replace=False)

    await message.answer(text, reply_markup=markup, disable_web_page_preview=True)


# --- Обработка лайков / дизлайков ---
@router.callback_query(F.data.startswith("vote_"))
async def handle_vote(callback: types.CallbackQuery, bot: Bot):
    parts = callback.data.split("_")
    proxy_id = int(parts[1])
    is_upvote = parts[2] == "up"
    is_premium = callback.from_user.is_premium or False

    success, msg = await add_or_update_vote(callback.from_user.id, proxy_id, is_upvote, is_premium)

    if not success:
        await callback.answer(msg, show_alert=True)
        return

    await callback.answer(msg)

    proxy = await get_proxy_by_id(proxy_id)
    bot_info = await bot.get_me()

    # Снова та же функция!
    text = get_public_proxy_text(proxy, bot_info.username)
    markup = get_proxy_vote_keyboard(proxy.id, proxy.url, proxy.likes, proxy.dislikes)

    try:
        await callback.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        pass