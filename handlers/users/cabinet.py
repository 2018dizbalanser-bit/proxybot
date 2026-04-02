from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.exc import IntegrityError

from database.models import Proxy
from database.connect import async_session
from database.requests.get import get_user_proxies, get_proxy_by_id, get_user, get_user_liked_proxies, \
    get_user_stats_for_cabinet, get_bot_settings
from database.requests.delete import delete_proxy_db
from keyboards.inline import get_cabinet_main_keyboard, get_my_proxies_keyboard, get_proxy_manage_keyboard, \
    get_limit_reached_keyboard, get_sponsor_tariffs_keyboard, get_liked_proxies_keyboard
from utils.ping import ping_proxy, parse_proxy_url

router = Router()


class AddProxyState(StatesGroup):
    waiting_for_url = State()


class SponsorState(StatesGroup):
    waiting_for_forward = State()


# --- 1. Отрисовка ГЛАВНОГО меню кабинета ---
async def _render_main_cabinet(user: types.User, send_method):
    # Получаем свежую статистику юзера
    stats = await get_user_stats_for_cabinet(user.id)

    # Заголовок и ID с твоими эмодзи
    text = f"👤 <b>Личный кабинет</b>\n\n"
    text += (f"<tg-emoji emoji-id='5974526806995242353'>👍</tg-emoji> "
             f"Ваш ID: <code>{user.id}</code>\n\n")

    # НОВЫЙ БЛОК: Статистика активности
    text += (f"<tg-emoji emoji-id='5974310710010711597'>👍</tg-emoji>"
             f" <b>Ваша активность:</b>\n"
             f"<tg-emoji emoji-id='5974350313904147369'>👍</tg-emoji>"
             f"  Просмотрено прокси: <b>{stats['viewed']}</b>\n"
             f"<tg-emoji emoji-id='5854868854919925803'>👍</tg-emoji>"
             f"  Сохранено в избранное: <b>{stats['liked']}</b>\n")

    # Если юзер - партнер, показываем его серверы
    if stats['added'] > 0:
        text += (f"<tg-emoji emoji-id='5974104203688152439'>👍</tg-emoji>"
                 f"  Добавлено серверов: <b>{stats['added']}</b>\n")

    text += "\n"  # Отступ перед пояснениями

    # Пояснения и призыв к действию
    text += (f"⭐ <b>Избранное:</b> здесь хранятся прокси, которым вы поставили лайк.\n"
             f"⚙️ <b>Панель партнера:</b> добавление и продвижение собственных серверов.\n\n"
             f"<i>Выберите нужный раздел:</i>")

    await send_method(text, reply_markup=get_cabinet_main_keyboard())


@router.message(F.text == "👤 Личный кабинет")
async def show_cabinet_msg(message: types.Message):
    await _render_main_cabinet(message.from_user, message.answer)


@router.callback_query(F.data == "back_to_cabinet")
async def back_to_cabinet_call(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await _render_main_cabinet(callback.from_user, callback.message.edit_text)
    await callback.answer()


# --- 2. Список избранных прокси ---
@router.callback_query(F.data == "liked_proxies_list")
async def show_liked_proxies_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    proxies = await get_user_liked_proxies(user_id)

    if not proxies:
        text = (
            "⭐ <b>Избранные прокси</b>\n\n"
            "У вас пока нет сохраненных серверов.\n\n"
            "<i>💡 Подсказка: Ставьте лайк (👍) быстрым прокси в общей ленте, и они навсегда сохранятся здесь!</i>"
        )
        markup = InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_cabinet")
        ).as_markup()
        await callback.message.edit_text(text, reply_markup=markup)
        return

    await callback.message.edit_text(
        "⭐ <b>Ваши избранные прокси:</b>\n\n"
        "Нажмите на сервер, чтобы получить ссылку для подключения:",
        reply_markup=get_liked_proxies_keyboard(proxies)
    )


# --- 3. Карточка конкретного избранного прокси ---
@router.callback_query(F.data.startswith("show_liked_prx_"))
async def show_specific_liked_proxy(callback: types.CallbackQuery, bot: Bot):
    proxy_id = int(callback.data.split("_")[3])
    proxy = await get_proxy_by_id(proxy_id)

    if not proxy or not proxy.is_active:
        await callback.answer("Этот сервер больше недоступен 😔", show_alert=True)
        return

    uptime = round((proxy.success_checks / proxy.total_checks) * 100, 1) if proxy.total_checks > 0 else 100
    host = proxy.url.split("server=")[1].split("&")[0] if "server=" in proxy.url else "Скрытый адрес"

    text = (
        f"⭐ <b>Избранный прокси #{proxy.id}</b>\n"
        f"<code>{host}</code>\n\n"
        f"🟢 Стабильность: <b>{uptime}%</b>\n\n"
        f"Нажмите кнопку ниже, чтобы применить настройки к вашему Telegram."
    )

    markup = InlineKeyboardBuilder()
    markup.row(types.InlineKeyboardButton(text="🚀 Подключиться", url=proxy.url))
    markup.row(types.InlineKeyboardButton(text="🔙 Назад к списку", callback_data="liked_proxies_list"))

    await callback.message.edit_text(text, reply_markup=markup.as_markup(), disable_web_page_preview=True)


# --- Вкладка "Мои прокси" ---
@router.callback_query(F.data == "my_proxies")
async def show_my_proxies_call(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    proxies = await get_user_proxies(user_id)

    # Достаем юзера из базы, чтобы получить актуальный лимит
    user = await get_user(user_id)
    user_limit = user.proxy_limit if (user and user.proxy_limit is not None) else 3

    text = f"🌐 <b>Ваши прокси-серверы</b>\n\n"
    # Теперь цифра лимита подтягивается динамически из БД!
    text += f"У вас добавлено: <b>{len(proxies)} из {user_limit}</b>\n\n"

    if not proxies:
        text += "<i>У вас пока нет серверов. Добавьте первый, чтобы получить реферальную ссылку для продвижения!</i>"
    else:
        text += "<i>Нажмите на прокси для просмотра статистики и управления:</i>"

    await callback.message.edit_text(text, reply_markup=get_my_proxies_keyboard(proxies))


# --- 1. Меню выбора тарифа ОП ---
@router.callback_query(F.data.startswith("sponsor_menu_"))
async def sponsor_menu_handler(callback: types.CallbackQuery):
    proxy_id = int(callback.data.split("_")[2])

    text = (
        "📢 <b>Покупка Обязательной Подписки (ОП)</b>\n\n"
        "Все пользователи, которые перейдут по вашей реферальной ссылке, "
        "будут обязаны подписаться на ваш канал.\n\n"
        "Выберите желаемый тариф:"
    )
    settings = await get_bot_settings()
    price_sponsor_7 = settings.price_sponsor_7
    price_sponsor_30 = settings.price_sponsor_30
    await callback.message.edit_text(text, reply_markup=get_sponsor_tariffs_keyboard(proxy_id, price_sponsor_7, price_sponsor_30))


# --- 2. Нажатие на конкретный тариф (7 или 30) ---
# Ловим buy_sponsor_X_Y
@router.callback_query(F.data.startswith("buy_sponsor_"))
async def start_buy_sponsor(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    proxy_id = int(parts[2])
    days = int(parts[3])

    # Запоминаем ID прокси и количество дней в FSM
    await state.update_data(proxy_id=proxy_id, days=days)

    text = (
        f"📢 <b>Привязка канала (Тариф: {days} дней)</b>\n\n"
        f"👇 <b>Как привязать:</b>\n"
        f"1. Добавьте нашего бота в администраторы вашего канала.\n"
        f"2. Перешлите сюда любое сообщение из этого канала."
    )

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text="🔙 Отмена", callback_data=f"sponsor_menu_{proxy_id}")
        ).as_markup()
    )
    await state.set_state(SponsorState.waiting_for_forward)


# --- 3. Получение пересланного сообщения и выставление счета ---
@router.message(SponsorState.waiting_for_forward)
async def process_sponsor_channel(message: types.Message, state: FSMContext, bot: Bot):
    if not message.forward_from_chat or message.forward_from_chat.type != 'channel':
        await message.answer("⚠️ Пожалуйста, перешлите сообщение именно из <b>канала</b>.")
        return

    channel_id = message.forward_from_chat.id
    channel_title = message.forward_from_chat.title

    try:
        chat_member = await bot.get_chat_member(channel_id, bot.id)
        if chat_member.status not in ['administrator', 'creator']:
            await message.answer("❌ Бот не является администратором в этом канале.")
            return
    except Exception:
        await message.answer("❌ Ошибка доступа. Убедитесь, что бот добавлен в канал как администратор!")
        return

    data = await state.get_data()
    proxy_id = data['proxy_id']
    days = data['days']

    settings = await get_bot_settings()
    price_sponsor_7 = settings.price_sponsor_7
    price_sponsor_30 = settings.price_sponsor_30


    # Определяем цену из конфига в зависимости от дней
    amount = price_sponsor_30 if days == 30 else price_sponsor_7

    # Формируем Payload: добавляем туда количество дней! (sponsor_15_-100123_30)
    payload = f"sponsor_{proxy_id}_{channel_id}_{days}"

    prices = [types.LabeledPrice(label=f"ОП на {days} дней", amount=amount)]

    await message.answer_invoice(
        title="Обязательная подписка",
        description=f"Привязка канала «{channel_title}» к прокси #{proxy_id} на {days} дней.",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=prices
    )
    await state.clear()


# --- 3. Заглушки для будущих функций монетизации ---
@router.callback_query(
    F.data.in_(["buy_vip"])
)
async def future_features_stub(callback: types.CallbackQuery):
    await callback.answer("🛠 Эта функция находится в разработке и скоро появится!", show_alert=True)


from datetime import datetime  # добавь в импорты наверху!


@router.callback_query(F.data.startswith("proxy_manage_"))
async def manage_specific_proxy(callback: types.CallbackQuery, bot: Bot):
    proxy_id = int(callback.data.split("_")[2])
    proxy = await get_proxy_by_id(proxy_id)

    if not proxy or proxy.owner_id != callback.from_user.id:
        return

    uptime = round((proxy.success_checks / proxy.total_checks) * 100, 1) if proxy.total_checks > 0 else 100
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=prx_{proxy.id}"
    status = "🟢 Активен" if proxy.is_active else "🔴 Недоступен (мертв)"

    has_sponsor = bool(proxy.sponsor_until and proxy.sponsor_until > datetime.utcnow())
    # ПРОВЕРЯЕМ БУСТ
    is_boosted = bool(proxy.boost_until and proxy.boost_until > datetime.utcnow())

    text = (
        f"⚙️ <b>Прокси #{proxy.id}</b>\n"
        f"<code>{proxy.url}</code>\n\n"
        f"Статус: {status}\n"
        f"Стабильность: <b>{uptime}%</b> | Скор: <b>{round(proxy.score, 1)}</b>\n"
        f"Голоса пользователей: 👍 {proxy.likes} | 👎 {proxy.dislikes}\n\n"
    )

    # ЕСЛИ ЕСТЬ БУСТ - ВЫВОДИМ В ТЕКСТ
    if is_boosted:
        text += f"🚀 <b>Буст в ТОП:</b> Активен до <code>{proxy.boost_until.strftime('%d.%m %H:%M')}</code>\n"

    if has_sponsor:
        text += f"📢 <b>ОП:</b> Активна до <code>{proxy.sponsor_until.strftime('%d.%m %H:%M')}</code>\n"

    text += (
        f"\n🔗 <b>Ваша реферальная ссылка:</b>\n<code>{ref_link}</code>\n\n"
        f"<i>Размещайте ссылку в своем канале! Люди будут получать ваш прокси, а вы — рейтинг.</i>"
    )

    # ПЕРЕДАЕМ is_boosted В КЛАВИАТУРУ
    await callback.message.edit_text(
        text,
        reply_markup=get_proxy_manage_keyboard(proxy.id, has_sponsor, proxy.is_public, is_boosted),
        disable_web_page_preview=True
    )


# --- 4. Удаление прокси ---
@router.callback_query(F.data.startswith("user_delete_prx_"))
async def delete_user_proxy(callback: types.CallbackQuery):
    proxy_id = int(callback.data.split("_")[3])
    proxy = await get_proxy_by_id(proxy_id)

    # Строгая проверка владельца перед удалением
    if proxy and proxy.owner_id == callback.from_user.id:
        await delete_proxy_db(proxy_id)
        await callback.answer("✅ Прокси успешно удален!", show_alert=True)
    else:
        await callback.answer("❌ Ошибка: нет прав для удаления!", show_alert=True)

    # Возвращаемся в обновленный кабинет
    await _render_main_cabinet(callback.from_user, callback.message.edit_text)


# --- Нажатие на "Добавить прокси" (с проверкой лимита) ---
@router.callback_query(F.data == "user_add_proxy")
async def start_add_proxy(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    proxies = await get_user_proxies(user_id)

    # Достаем пользователя из БД, чтобы узнать его личный лимит
    user = await get_user(user_id)
    user_limit = user.proxy_limit if (user and user.proxy_limit is not None) else 3
    settings = await get_bot_settings()
    price_slot = settings.price_slot

    if len(proxies) >= user_limit:
        await callback.message.edit_text(
            f"❌ <b>Достигнут лимит серверов!</b>\n\n"
            f"Ваш текущий лимит: <b>{user_limit} шт.</b>\n"
            f"Чтобы добавить новые серверы, вы можете удалить старые или докупить дополнительные слоты.\n\n"
            f"<i>Стоимость 1 дополнительного слота навсегда: {price_slot} ⭐️</i>",
            reply_markup=get_limit_reached_keyboard(price_slot)
        )
        return

    # Если лимит не превышен — пускаем дальше
    await callback.message.edit_text(
        "🔗 Отправьте ссылку на ваш <b>MTProto</b> прокси.\n"
        "Она должна начинаться с <code>tg://proxy?server=</code> или <code>https://t.me/proxy?server=</code>\n\n"
        "<i>Нажмите кнопку ниже для отмены.</i>",
        reply_markup=InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text="🔙 Отмена", callback_data="my_proxies")
        ).as_markup(),
        disable_web_page_preview=True
    )
    await state.set_state(AddProxyState.waiting_for_url)
    await callback.answer()


# --- Выставление счета за слот ---
@router.callback_query(F.data == "buy_slot")
async def buy_slot_invoice(callback: types.CallbackQuery, bot: Bot):
    settings = await get_bot_settings()
    price_slot = settings.price_slot
    prices = [types.LabeledPrice(label="Дополнительный слот для прокси", amount=price_slot)]

    await callback.message.answer_invoice(
        title="Расширение лимита",
        description="Покупка +1 дополнительного места (навсегда) для вашего прокси-сервера в каталоге.",
        payload=f"slot_{callback.from_user.id}",  # Передаем ID юзера в payload
        provider_token="",  # Для Telegram Stars токен всегда пустой
        currency="XTR",
        prices=prices
    )
    await callback.answer()


# --- 6. Сохранение прокси с проверкой ---
@router.message(AddProxyState.waiting_for_url)
async def process_proxy_url(message: types.Message, state: FSMContext, bot: Bot):
    url = message.text.strip()

    if not (url.startswith("tg://proxy?server=") or url.startswith("https://t.me/proxy?server=")):
        await message.answer("⚠️ <b>Неверный формат!</b>\nОтправьте правильную ссылку MTProto.")
        return

    wait_msg = await message.answer("⏳ <i>Пингую ваш сервер, подождите...</i>")

    # 1. Достаем IP и порт из ссылки
    host, port = parse_proxy_url(url)
    if not host or not port:
        await wait_msg.edit_text("❌ <b>Не удалось извлечь IP и порт из ссылки. Проверьте формат!</b>")
        return

    # 2. Используем наш новый быстрый TCP-пинг
    is_alive, resp_time = await ping_proxy(host, port)

    # Если is_alive == False (сервер не ответил на рукопожатие)
    if not is_alive:
        await wait_msg.edit_text(
            "❌ <b>Сервер недоступен или мертв!</b>\n"
            "Я не могу добавить нерабочий прокси в каталог."
        )
        return

    # 3. Считаем начальный рейтинг по новой формуле
    # (Как в воркере: лайки - дизлайки - время_ответа/100). Лайков пока 0.
    initial_score = float(-(resp_time / 100.0))

    async with async_session() as session:
        try:
            new_proxy = Proxy(
                url=url,
                owner_id=message.from_user.id,
                score=initial_score,
                is_active=True,
                success_checks=1,
                total_checks=1
            )
            session.add(new_proxy)
            await session.commit()
            await session.refresh(new_proxy)

            bot_info = await bot.get_me()
            ref_link = f"https://t.me/{bot_info.username}?start=prx_{new_proxy.id}"

            await wait_msg.edit_text(
                "✅ <b>Ваш прокси успешно проверен и добавлен!</b>\n\n"
                f"Пинг: <b>{int(resp_time)} мс</b> 🟢\n\n"
                f"🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>\n\n"
                "<i>Вернитесь в Личный кабинет для управления им.</i>",
                reply_markup=InlineKeyboardBuilder().row(
                    types.InlineKeyboardButton(text="🔙 В кабинет", callback_data="back_to_cabinet")
                ).as_markup(),
                disable_web_page_preview=True
            )
            await state.clear()

        except IntegrityError:
            await session.rollback()
            await wait_msg.edit_text(
                "❌ <b>Этот прокси уже существует в базе!</b>\nДобавление дубликатов запрещено.",
                reply_markup=InlineKeyboardBuilder().row(
                    types.InlineKeyboardButton(text="🔙 В кабинет", callback_data="back_to_cabinet")
                ).as_markup()
            )
            await state.clear()



# --- Меню активного спонсора ---
@router.callback_query(F.data.startswith("manage_sponsor_"))
async def manage_sponsor_handler(callback: types.CallbackQuery):
    proxy_id = int(callback.data.split("_")[2])
    proxy = await get_proxy_by_id(proxy_id)

    # Если спонсора нет или он истек - пишем ошибку
    if not proxy or not proxy.sponsor_until or proxy.sponsor_until < datetime.utcnow():
        await callback.answer("Спонсор не найден или срок действия истек.", show_alert=True)
        return

    text = (
        f"📢 <b>Управление спонсором (Прокси #{proxy_id})</b>\n\n"
        f"🔗 Привязанный канал: <a href='{proxy.sponsor_channel_url}'>Ссылка</a>\n"
        f"⏳ Активен до: <b>{proxy.sponsor_until.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
        f"<i>Все пользователи, переходящие по вашей реферальной ссылке, обязаны подписаться на этот канал. Вы можете отвязать его досрочно, но средства не возвращаются.</i>"
    )

    markup = InlineKeyboardBuilder()
    markup.row(types.InlineKeyboardButton(text="🗑 Отвязать канал", callback_data=f"unlink_sponsor_{proxy_id}"))
    markup.row(types.InlineKeyboardButton(text="🔙 Назад к прокси", callback_data=f"proxy_manage_{proxy_id}"))

    await callback.message.edit_text(text, reply_markup=markup.as_markup(), disable_web_page_preview=True)


# --- Досрочная отвязка спонсора ---
@router.callback_query(F.data.startswith("unlink_sponsor_"))
async def unlink_sponsor_handler(callback: types.CallbackQuery):
    proxy_id = int(callback.data.split("_")[2])

    async with async_session() as session:
        proxy = await session.get(Proxy, proxy_id)
        if proxy and proxy.owner_id == callback.from_user.id:
            proxy.sponsor_channel_id = None
            proxy.sponsor_channel_url = None
            proxy.sponsor_until = None
            await session.commit()

    await callback.message.edit_text(
        "✅ Спонсорский канал успешно отвязан.",
        reply_markup=InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text="🔙 Назад к прокси", callback_data=f"proxy_manage_{proxy_id}")
        ).as_markup()
    )


@router.callback_query(F.data.startswith("toggle_public_"))
async def toggle_public_handler(callback: types.CallbackQuery, bot: Bot):
    proxy_id = int(callback.data.split("_")[2])

    new_status = True
    async with async_session() as session:
        proxy = await session.get(Proxy, proxy_id)
        if proxy and proxy.owner_id == callback.from_user.id:
            proxy.is_public = not proxy.is_public
            new_status = proxy.is_public
            await session.commit()

    # ПОКАЗЫВАЕМ ПОНЯТНОЕ ВСПЛЫВАЮЩЕЕ ОКНО
    if new_status:
        await callback.answer(
            "👁 Теперь этот прокси виден ВСЕМ пользователям в общей выдаче каталога!",
            show_alert=True
        )
    else:
        await callback.answer(
            "🚫 Прокси скрыт из общей выдачи! Теперь люди смогут подключиться к нему ТОЛЬКО по вашей реферальной ссылке.",
            show_alert=True
        )

    # Перерисовываем меню с обновленной кнопкой
    await manage_specific_proxy(callback, bot)


@router.callback_query(F.data.startswith("buy_boost_"))
async def buy_boost_handler(callback: types.CallbackQuery):
    proxy_id = int(callback.data.split("_")[2])
    settings = await get_bot_settings()
    price_boost = settings.price_boost

    prices = [types.LabeledPrice(label="Буст в ТОП (24 часа)", amount=price_boost)]

    await callback.message.answer_invoice(
        title="Ракета для прокси 🚀",
        description=f"Ваш прокси #{proxy_id} будет иметь приоритет в выдаче над всеми бесплатными серверами в течение 24 часов.",
        payload=f"boost_{proxy_id}",
        provider_token="",  # Stars
        currency="XTR",
        prices=prices
    )
    await callback.answer()