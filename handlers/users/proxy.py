import asyncio

from aiogram import Router, F, types, Bot
from database.requests.get import get_all_channels, get_best_proxy
from keyboards.inline import get_subscription_keyboard, get_proxy_control_keyboard
from utils.ping import parse_proxy_url
from utils.subscription import get_unsubscribed_channels

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
        await send_best_proxy(message)


@router.callback_query(F.data == "check_subscription")
async def check_sub_handler(callback: types.CallbackQuery, bot: Bot):
    channels = await get_all_channels()
    unsubscribed = await get_unsubscribed_channels(bot, callback.from_user.id, channels)

    if not unsubscribed:  # Список пуст, значит подписан на все!
        await callback.answer("✅ Подписка подтверждена!", show_alert=False)
        await send_best_proxy(callback.message, edit_message=True)
    else:
        await callback.answer("❌ Вы подписались не на все каналы!", show_alert=True)
        # КИЛЛЕР-ФИЧА: Обновляем клавиатуру!
        # Если юзер подписался на 1 из 2 каналов, кнопка подписанного канала исчезнет.
        await callback.message.edit_reply_markup(
            reply_markup=get_subscription_keyboard(unsubscribed)
        )


# --- Вспомогательная функция для выдачи прокси ---
async def send_best_proxy(message: types.Message, edit_message: bool = False, exclude_id: int = None):
    """
    Ищет лучший прокси и отправляет его в дружелюбном стиле (Вариант 3).
    """
    proxy = await get_best_proxy(exclude_id)

    if not proxy:
        text = "😔 <b>К сожалению, сейчас нет доступных рабочих прокси.</b>\nЗагляните немного позже!"
        markup = None
    else:
        # Получаем хост и порт для гиперссылки
        host, port = parse_proxy_url(proxy.url)
        # Если распарсить не удалось, используем понятный текст
        display_name = f"{host}:{port}" if host and port else "Нажми сюда для подключения"

        uptime = 100
        if proxy.total_checks > 0:
            uptime = round((proxy.success_checks / proxy.total_checks) * 100, 1)

        # Текст Варианта 3: Дружелюбный и простой
        text = (
            f"⚡️ <b>Готово! Подключаемся?</b>\n\n"
            f"Нажми на ссылку, чтобы Telegram всегда был онлайн:\n"
            f"👉 <b><a href='{proxy.url}'>{display_name}</a></b>\n\n"
            f"Если этот сервер начнет «подтормаживать», я подберу тебе новый в одно нажатие.\n\n"
            f"🟢 Стабильность: <b>{uptime}%</b>"
        )

        # Кнопка для замены прокси
        markup = get_proxy_control_keyboard(proxy.id)

    if edit_message:
        await message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    else:
        await message.answer(text, reply_markup=markup, disable_web_page_preview=True)


@router.callback_query(F.data.startswith("replace_proxy_"))
async def replace_proxy_handler(callback: types.CallbackQuery, bot: Bot):
    # Достаем ID прокси, который сейчас видит юзер
    current_proxy_id = int(callback.data.split("_")[2])

    # --- ИЛЛЮЗИЯ ПОДБОРА ---
    # Список фраз, которые будут сменять друг друга
    steps = [
        "🔄 <b>Связываюсь с узлами мониторинга...</b>",
        "📡 <b>Проверяю доступность резервных шлюзов...</b>",
        "⚡️ <b>Замеряю минимальный RTT (пинг)...</b>",
        "💎 <b>Оптимальный сервер найден! Формирую ключ...</b>"
    ]

    for step_text in steps:
        try:
            await callback.message.edit_text(step_text)
            await asyncio.sleep(0.6) # Пауза между фразами
        except Exception:
            # Если текст не изменился или сообщение удалено — просто идем дальше
            pass

    # Вызываем финальную выдачу, как и раньше
    await send_best_proxy(callback.message, edit_message=True, exclude_id=current_proxy_id)