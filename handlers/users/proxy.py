import asyncio

from aiogram import Router, F, types, Bot

from database.requests.add import add_or_update_vote
from database.requests.get import get_all_channels, get_best_proxy, get_proxy_by_id, mark_proxy_viewed, check_if_viewed
from keyboards.inline import get_subscription_keyboard, get_proxy_vote_keyboard
from utils.i18n import t, all_values
from utils.subscription import get_unsubscribed_channels
from utils.texts import get_proxy_card_text

router = Router()


@router.message(F.text.in_(all_values('btn_get_proxy')))
async def get_proxy_handler(message: types.Message, bot: Bot, lang: str):
    channels = await get_all_channels()
    unsubscribed = await get_unsubscribed_channels(bot, message.from_user.id, channels)

    if unsubscribed:
        await message.answer(
            t('proxy_subscribe_required', lang),
            reply_markup=get_subscription_keyboard(unsubscribed, lang)
        )
    else:
        # Подписан на все (или обязательных каналов вообще нет)
        # Переключаем reply-клавиатуру на действия с прокси
        await message.answer("🎯 <i>Подбираю лучший сервер...</i>", reply_markup=proxy_actions_kb())
        # ЯВНО УКАЗЫВАЕМ is_replace=False (работает приоритет ПРОМО)
        await send_best_proxy(message, bot=bot, user_id=message.from_user.id, is_replace=False)

@router.callback_query(F.data == "check_subscription")
async def check_sub_handler(callback: types.CallbackQuery, bot: Bot, lang: str):
    channels = await get_all_channels()
    unsubscribed = await get_unsubscribed_channels(bot, callback.from_user.id, channels)

    if not unsubscribed:  # Список пуст, значит подписан на все!
        await callback.answer("✅ Подписка подтверждена!", show_alert=False)
        # Переключаем reply-клавиатуру на действия с прокси
        await callback.message.answer("🎯 <i>Подбираю лучший сервер...</i>", reply_markup=proxy_actions_kb())
        await send_best_proxy(callback.message, bot=bot, edit_message=True)
    else:
        await callback.answer(t('proxy_sub_not_all', lang), show_alert=True)
        await callback.message.edit_reply_markup(
            reply_markup=get_subscription_keyboard(unsubscribed, lang)
        )


async def send_best_proxy(message: types.Message, bot: Bot, user_id: int, edit_message: bool = False,
                          exclude_id: int = None, is_replace: bool = False, lang: str = 'ru'):
    proxy = await get_best_proxy(user_id, exclude_id, is_replace)

    if not proxy:
        text = t('proxy_not_found', lang)
        if edit_message:
            await message.edit_text(text, reply_markup=None)
        else:
            await message.answer(text, reply_markup=None)
        return

    bot_info = await bot.get_me()
    is_already_seen = await check_if_viewed(user_id, proxy.id)
    await mark_proxy_viewed(user_id, proxy.id)

    text = get_proxy_card_text(proxy, bot_info.username, is_viewed=is_already_seen, lang=lang)
    markup = get_proxy_vote_keyboard(
        proxy_id=proxy.id,
        url=proxy.url,
        likes=proxy.likes,
        dislikes=proxy.dislikes,
        bot_username=bot_info.username,
        show_replace=True,
        lang=lang
    )

    if edit_message:
        try:
            await message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except Exception:
            await message.answer(text, reply_markup=markup, disable_web_page_preview=True)
    else:
        await message.answer(text, reply_markup=markup, disable_web_page_preview=True)


@router.callback_query(F.data.startswith("replace_proxy_"))
async def replace_proxy_handler(callback: types.CallbackQuery, bot: Bot, lang: str):
    proxy_id = int(callback.data.split("_")[2])

    try:
        await callback.message.delete()
        emoji = await callback.message.answer(
            f"<tg-emoji emoji-id='5388953246486269495'>👍</tg-emoji>"
        )
        await asyncio.sleep(0.6)
        await emoji.delete()
    except Exception:
        pass

    await send_best_proxy(
        message=callback.message,
        bot=bot,
        user_id=callback.from_user.id,
        edit_message=False,
        exclude_id=proxy_id,
        is_replace=True,
        lang=lang
    )
    await callback.answer()


async def send_specific_proxy(message: types.Message, proxy_id: int, bot: Bot, lang: str = 'ru'):
    proxy = await get_proxy_by_id(proxy_id)

    if not proxy or not proxy.is_active:
        await message.answer(t('proxy_unavailable', lang))
        return

    bot_info = await bot.get_me()
    text = get_proxy_card_text(proxy, bot_info.username, is_direct_link=True, is_viewed=False, lang=lang)
    markup = get_proxy_vote_keyboard(
        proxy_id=proxy.id,
        url=proxy.url,
        likes=proxy.likes,
        dislikes=proxy.dislikes,
        bot_username=bot_info.username,
        show_replace=False,
        lang=lang
    )
    await message.answer(text, reply_markup=markup, disable_web_page_preview=True)


@router.callback_query(F.data.startswith("vote_"))
async def handle_vote(callback: types.CallbackQuery, bot: Bot, lang: str):
    parts = callback.data.split("_")
    proxy_id = int(parts[1])
    is_upvote = parts[2] == "up"
    is_premium = callback.from_user.is_premium or False

    success, msg_key = await add_or_update_vote(callback.from_user.id, proxy_id, is_upvote, is_premium)

    if not success:
        await callback.answer(t(msg_key, lang), show_alert=True)
        return

    await callback.answer(t(msg_key, lang))

    proxy = await get_proxy_by_id(proxy_id)
    bot_info = await bot.get_me()

    text = get_proxy_card_text(proxy, bot_info.username, is_direct_link=False, is_viewed=True, lang=lang)
    markup = get_proxy_vote_keyboard(
        proxy_id=proxy.id,
        url=proxy.url,
        likes=proxy.likes,
        dislikes=proxy.dislikes,
        bot_username=bot_info.username,
        show_replace=True,
        lang=lang
    )

    try:
        await callback.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception as e:
        print(f"Ошибка при обновлении интерфейса лайка: {e}")

