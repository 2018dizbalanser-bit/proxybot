import asyncio

from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext

from database.requests.add import add_or_update_vote
from database.requests.get import get_all_channels, get_best_proxy, get_proxy_by_id, mark_proxy_viewed, check_if_viewed
from keyboards.inline import get_subscription_keyboard, get_proxy_vote_keyboard
from keyboards.reply import proxy_keyboard, main_keyboard
from utils.i18n import t, all_values
from utils.subscription import get_unsubscribed_channels
from utils.texts import get_proxy_card_text

router = Router()


@router.message(F.text.in_(all_values('btn_get_proxy')))
async def get_proxy_handler(message: types.Message, bot: Bot, lang: str, state: FSMContext):
    channels = await get_all_channels()
    unsubscribed = await get_unsubscribed_channels(bot, message.from_user.id, channels)

    if unsubscribed:
        await message.answer(
            t('proxy_subscribe_required', lang),
            reply_markup=get_subscription_keyboard(unsubscribed, lang)
        )
    else:
        # Переключаем reply-клавиатуру на действия с прокси
        await message.answer("🎯 ...", reply_markup=proxy_keyboard(lang))
        await send_best_proxy(message, bot=bot, user_id=message.from_user.id,
                              is_replace=False, lang=lang, state=state)


@router.callback_query(F.data == "check_subscription")
async def check_sub_handler(callback: types.CallbackQuery, bot: Bot, lang: str, state: FSMContext):
    channels = await get_all_channels()
    unsubscribed = await get_unsubscribed_channels(bot, callback.from_user.id, channels)

    if not unsubscribed:
        await callback.answer(t('proxy_sub_confirmed', lang), show_alert=False)
        # Переключаем reply-клавиатуру на действия с прокси
        await callback.message.answer("🎯 ...", reply_markup=proxy_keyboard(lang))
        await send_best_proxy(callback.message, bot=bot, user_id=callback.from_user.id,
                              edit_message=True, lang=lang, state=state)
    else:
        await callback.answer(t('proxy_sub_not_all', lang), show_alert=True)
        await callback.message.edit_reply_markup(
            reply_markup=get_subscription_keyboard(unsubscribed, lang)
        )


async def send_best_proxy(message: types.Message, bot: Bot, user_id: int, edit_message: bool = False,
                          exclude_id: int = None, is_replace: bool = False, lang: str = 'ru',
                          state: FSMContext | None = None):
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
        lang=lang
    )

    if edit_message:
        try:
            sent = await message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except Exception:
            sent = await message.answer(text, reply_markup=markup, disable_web_page_preview=True)
    else:
        sent = await message.answer(text, reply_markup=markup, disable_web_page_preview=True)

    # Запоминаем ID карточки для последующей "замены" по кнопке "🔄 Другой прокси"
    if state is not None and hasattr(sent, 'message_id'):
        await state.update_data(last_proxy_msg_id=sent.message_id)


@router.callback_query(F.data.startswith("replace_proxy_"))
async def replace_proxy_handler(callback: types.CallbackQuery, bot: Bot, lang: str, state: FSMContext):
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
        lang=lang,
        state=state
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
        lang=lang
    )

    try:
        await callback.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception as e:
        print(f"Ошибка при обновлении интерфейса лайка: {e}")


@router.message(F.text.in_(all_values('btn_other_proxy')))
async def other_proxy_text_handler(message: types.Message, bot: Bot, lang: str, state: FSMContext):
    # Текстовая reply-кнопка "🔄 Другой прокси"
    # Проверяем обязательные подписки так же, как в get_proxy_handler
    channels = await get_all_channels()
    unsubscribed = await get_unsubscribed_channels(bot, message.from_user.id, channels)
    if unsubscribed:
        await message.answer(
            t('proxy_subscribe_required', lang),
            reply_markup=get_subscription_keyboard(unsubscribed, lang)
        )
        return

    # 1) Удаляем сообщение-тап юзера ("🔄 Другой прокси"), чтобы чат не засорялся
    try:
        await message.delete()
    except Exception:
        pass

    # 2) Удаляем старую карточку прокси (если знаем её ID)
    data = await state.get_data()
    last_msg_id = data.get('last_proxy_msg_id')
    if last_msg_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=last_msg_id)
        except Exception:
            pass

    # 3) Кратковременная 👍-анимация, как в старом replace_proxy_handler
    try:
        emoji = await bot.send_message(
            chat_id=message.chat.id,
            text="<tg-emoji emoji-id='5388953246486269495'>👍</tg-emoji>"
        )
        await asyncio.sleep(0.1)
        await emoji.delete()
    except Exception:
        pass

    # 4) Отправляем новую карточку и запоминаем её ID
    await send_best_proxy(
        message=message,
        bot=bot,
        user_id=message.from_user.id,
        is_replace=True,
        lang=lang,
        state=state
    )


@router.message(F.text.in_(all_values('btn_main_menu')))
async def main_menu_text_handler(message: types.Message, lang: str):
    # Текстовая reply-кнопка "🔝 Главное меню"
    await message.answer("🏠", reply_markup=main_keyboard(lang))



@router.callback_query(F.data.startswith("no_connect_"))
async def no_connect_handler(callback: types.CallbackQuery, lang: str):
    await callback.answer(t('proxy_tips_alert', lang), show_alert=True)
