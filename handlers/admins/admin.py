import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data.config import ADMIN_IDS
from database.requests.get import get_all_users, get_all_channels, get_all_proxies, get_detailed_stats, \
    mark_user_inactive
from database.requests.add import add_channel
from database.requests.delete import delete_channel_db, delete_proxy_db
from database.requests.get import get_admin_analytics, get_bot_settings, get_referral_stats, update_bot_price
from keyboards.inline import (admin_main_kb, admin_channels_kb,
                                    admin_back_kb, get_admin_prices_kb, get_refs_pagination_kb)
from utils.ping import ping_proxy, parse_proxy_url

router = Router()

# Фильтр для проверки, что юзер - админ
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


class AdminState(StatesGroup):
    add_channel = State()
    broadcast = State()
    waiting_for_channel_url = State()  # НОВОЕ СОСТОЯНИЕ
    waiting_for_new_price = State()



# --- ЕДИНЫЙ ДАШБОРД (Твоя старая стата + Новые финансы) ---
async def render_admin_panel(send_method):
    # Получаем старые данные по юзерам
    stats = await get_detailed_stats()
    # Получаем новые данные по финансам и серверам
    total_proxies, active_proxies, _, finances = await get_admin_analytics()

    total_stars = sum(finances.values())

    text = (
        "👑 <b>Панель администратора</b>\n\n"

        "👥 <b>Аудитория:</b>\n"
        f"Всего пользователей: <b>{stats['total']}</b> (Активных: {stats['active']})\n"
        f"Новые сегодня: <b>+{stats['today']}</b> | Вчера: <b>+{stats['yesterday']}</b>\n"
        f"За неделю: <b>+{stats['week']}</b> | За месяц: <b>+{stats['month']}</b>\n\n"

        "🌐 <b>Сеть прокси:</b>\n"
        f"Всего в базе: <b>{total_proxies}</b>\n"
        f"Активных: <b>{active_proxies}</b> 🟢\n"
        f"Мертвых: <b>{total_proxies - active_proxies}</b> 🔴\n\n"

        "💰 <b>Доходы (Telegram Stars):</b>\n"
        f"Всего заработано: <b>{total_stars} ⭐️</b>\n"
        f"├ Слоты: <b>{finances.get('slot', 0)} ⭐️</b>\n"
        f"├ Спонсорство (ОП): <b>{finances.get('sponsor', 0)} ⭐️</b>\n"
        f"└ Бусты в ТОП: <b>{finances.get('boost', 0)} ⭐️</b>\n\n"

        "<i>Выберите действие:</i>"
    )
    await send_method(text, reply_markup=admin_main_kb())


@router.message(Command("admin"))
async def admin_start(message: types.Message, state: FSMContext):
    await state.clear()
    await render_admin_panel(message.answer)


@router.callback_query(F.data == "admin_main")
async def admin_main_call(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await render_admin_panel(callback.message.edit_text)
    await callback.answer()


@router.callback_query(F.data == "admin_channels")
async def show_channels(callback: types.CallbackQuery):
    channels = await get_all_channels()
    await callback.message.edit_text(
        "📢 <b>Управление обязательной подпиской</b>\nНажмите на канал, чтобы удалить его:",
        reply_markup=admin_channels_kb(channels)
    )

@router.callback_query(F.data.startswith("del_ch_"))
async def del_channel_handler(callback: types.CallbackQuery):
    ch_id = int(callback.data.split("_")[2])
    await delete_channel_db(ch_id)
    await callback.answer("✅ Канал удален!")
    await show_channels(callback)

@router.callback_query(F.data == "add_channel")
async def add_channel_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ <b>Добавление канала</b>\n\n"
        "➡️ <b>Способ 1 (Легкий):</b> Просто перешлите сюда любое сообщение из нужного канала.\n"
        "➡️ <b>Способ 2 (Ручной):</b> Отправьте <code>ID | НАЗВАНИЕ | ССЫЛКА</code>\n\n"
        "<i>⚠️ Бот уже должен быть администратором канала!</i>",
        reply_markup=admin_back_kb()
    )
    await state.set_state(AdminState.add_channel)

@router.message(AdminState.add_channel)
async def process_add_channel(message: types.Message, state: FSMContext):
    # ПРОВЕРКА 1: Сообщение переслано из канала?
    if message.forward_origin and message.forward_origin.type == 'channel':
        chat = message.forward_origin.chat
        ch_id = chat.id
        title = chat.title
        username = chat.username

        if username:
            # Публичный канал (ссылка t.me/username)
            url = f"https://t.me/{username}"
            await add_channel(ch_id, title, url)
            await message.answer(f"✅ Публичный канал <b>{title}</b> успешно добавлен!", reply_markup=admin_main_kb())
            await state.clear()
        else:
            # Приватный канал (ссылку вытащить нельзя, запрашиваем у админа)
            await state.update_data(ch_id=ch_id, title=title)
            await state.set_state(AdminState.waiting_for_channel_url)
            await message.answer(
                f"🔒 Распознан приватный канал <b>{title}</b>.\n\n"
                f"🔗 Пожалуйста, отправьте пригласительную ссылку для этого канала:",
                reply_markup=admin_back_kb()
            )
        return

    # ПРОВЕРКА 2: Если это просто текст (старый ручной способ)
    try:
        parts = message.text.split("|")
        ch_id = int(parts[0].strip())
        title = parts[1].strip()
        url = parts[2].strip()
        await add_channel(ch_id, title, url)
        await message.answer("✅ Канал успешно добавлен!", reply_markup=admin_main_kb())
        await state.clear()
    except Exception:
        await message.answer("❌ Ошибка. Перешлите сообщение из канала или используйте формат 'ID | Название | Ссылка'.", reply_markup=admin_back_kb())

# Ловим ссылку для приватного канала
@router.message(AdminState.waiting_for_channel_url)
async def process_private_channel_url(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if not url.startswith("http"):
        await message.answer("❌ Это не похоже на ссылку. Отправьте ссылку начинающуюся с http/https:")
        return

    data = await state.get_data()
    await add_channel(data['ch_id'], data['title'], url)
    await message.answer(f"✅ Приватный канал <b>{data['title']}</b> успешно добавлен!", reply_markup=admin_main_kb())
    await state.clear()

# ==========================================
# 3. РАССЫЛКА (Старое)
# ==========================================
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📣 Отправьте сообщение для рассылки (можно с фото/видео):",
        reply_markup=admin_back_kb()
    )
    await state.set_state(AdminState.broadcast)


@router.message(AdminState.broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    users = await get_all_users()
    succ = 0
    msg = await message.answer(f"⏳ Рассылка запущена для {len(users)} пользователей...")

    for user in users:
        try:
            await message.send_copy(chat_id=user.tg_id)
            succ += 1
            await asyncio.sleep(0.05)  # Защита от спам-блока Telegram
        except Exception:
            # ВОТ ЗДЕСЬ МАГИЯ: если отправка не удалась (бот заблокирован),
            # мы сразу же записываем это в базу данных!
            await mark_user_inactive(user.tg_id)

    await msg.delete()

    # После рассылки статистика станет абсолютно точной!
    await message.answer(
        f"✅ Рассылка завершена!\n"
        f"Успешно доставлено: <b>{succ}</b> из <b>{len(users)}</b>.\n"
        f"<i>*Неактивные пользователи были автоматически исключены из статистики.</i>",
        reply_markup=admin_main_kb()
    )
    await state.clear()


# ==========================================
# 4. НАСТРОЙКИ ЦЕН (Новое)
# ==========================================
@router.callback_query(F.data == "admin_prices")
async def show_prices_handler(callback: types.CallbackQuery):
    settings = await get_bot_settings()
    text = "⚙️ <b>Управление ценами (в ⭐️ Stars)</b>\n\nВыберите услугу для изменения цены:"
    await callback.message.edit_text(text, reply_markup=get_admin_prices_kb(settings))


@router.callback_query(F.data.startswith("edit_price_"))
async def edit_price_start(callback: types.CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_price_", "price_")
    await state.update_data(field=field)
    await state.set_state(AdminState.waiting_for_new_price)

    await callback.message.edit_text(
        "✍️ Отправьте в чат новую стоимость (целое число) в Звездах:",
        reply_markup=InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text="Отмена", callback_data="admin_prices")
        ).as_markup()
    )


@router.message(AdminState.waiting_for_new_price)
async def process_new_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Пожалуйста, отправьте целое число!")
        return

    new_price = int(message.text)
    data = await state.get_data()
    field = data['field']

    await update_bot_price(field, new_price)
    await state.clear()

    await message.answer("✅ <b>Цена успешно обновлена!</b>")
    await render_admin_panel(message.answer)


# ==========================================
# 5. РЕФЕРАЛКИ И АНАЛИТИКА ТРАФИКА (Новое)
# ==========================================
@router.callback_query(F.data.startswith("admin_refs_"))
async def show_referrals(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[2])
    items_per_page = 10

    refs = await get_referral_stats()

    if not refs:
        await callback.message.edit_text(
            "🔗 Пока нет данных по рекламным переходам.",
            reply_markup=InlineKeyboardBuilder().row(
                types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")
            ).as_markup()
        )
        return

    total_pages = (len(refs) + items_per_page - 1) // items_per_page
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_refs = refs[start_idx:end_idx]

    text = f"🔗 <b>Статистика рекламных ссылок (Стр. {page + 1}/{total_pages}):</b>\n\n"
    for idx, ref in enumerate(page_refs, start=start_idx + 1):
        text += f"{idx}. <b>{ref['name']}</b> — {ref['users']} чел.\n"

    text += "\n<i>*Формат ссылки для закупа рекламы:\nhttps://t.me/ТвойБот?start=ИМЯ_МЕТКИ</i>"

    await callback.message.edit_text(text, reply_markup=get_refs_pagination_kb(page, total_pages))