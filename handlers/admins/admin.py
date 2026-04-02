import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from data.config import ADMIN_IDS
from database.requests.get import get_all_users, get_all_channels, get_all_proxies, get_users_stats, get_detailed_stats
from database.requests.add import add_channel, add_proxy
from database.requests.delete import delete_channel_db, delete_proxy_db
from keyboards.inline import admin_main_kb, admin_channels_kb, admin_proxies_kb, admin_back_kb
from utils.ping import ping_proxy

router = Router()

# Фильтр для проверки, что юзер - админ
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


class AdminState(StatesGroup):
    add_channel = State()
    add_proxy = State()
    broadcast = State()


async def get_admin_menu_text() -> str:
    stats = await get_detailed_stats()

    return (
        "⚙️ <b>Панель администратора</b>\n\n"
        "📊 <b>Общая статистика:</b>\n"
        f"👥 Всего пользователей: <b>{stats['total']}</b>\n"
        f"🟢 Активных: <b>{stats['active']}</b>\n"
        f"🔴 Удаленных: <b>{stats['total'] - stats['active']}</b>\n\n"
        "📈 <b>Новые пользователи:</b>\n"
        f"Сегодня: <b>+{stats['today']}</b>\n"
        f"Вчера: <b>+{stats['yesterday']}</b>\n"
        f"За неделю: <b>+{stats['week']}</b>\n"
        f"За месяц: <b>+{stats['month']}</b>\n\n"
        "Выберите действие:"
    )


# Теперь хендлеры будут использовать этот текст
@router.message(Command("admin"))
async def admin_start(message: types.Message, state: FSMContext):
    await state.clear()
    text = await get_admin_menu_text()
    await message.answer(text, reply_markup=admin_main_kb())


@router.callback_query(F.data == "admin_main")
async def admin_main_call(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    text = await get_admin_menu_text()
    await callback.message.edit_text(text, reply_markup=admin_main_kb())


# --- УПРАВЛЕНИЕ КАНАЛАМИ ---
@router.callback_query(F.data == "admin_channels")
async def show_channels(callback: types.CallbackQuery):
    channels = await get_all_channels()
    await callback.message.edit_text("📢 <b>Управление обязательной подпиской</b>\nНажмите на канал, чтобы удалить его:",
                                     reply_markup=admin_channels_kb(channels))


@router.callback_query(F.data.startswith("del_ch_"))
async def del_channel_handler(callback: types.CallbackQuery):
    ch_id = int(callback.data.split("_")[2])
    await delete_channel_db(ch_id)
    await callback.answer("✅ Канал удален!")
    await show_channels(callback)  # Обновляем список


@router.callback_query(F.data == "add_channel")
async def add_channel_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ <b>Добавление канала</b>\n\nОтправьте данные в формате:\n<code>ID_КАНАЛА | НАЗВАНИЕ | ССЫЛКА</code>\n\n<i>Пример: -10012345678 | Наш спонсор | https://t.me/sponsor</i>",
        reply_markup=admin_back_kb()
    )
    await state.set_state(AdminState.add_channel)


@router.message(AdminState.add_channel)
async def process_add_channel(message: types.Message, state: FSMContext):
    try:
        parts = message.text.split("|")
        ch_id = int(parts[0].strip())
        title = parts[1].strip()
        url = parts[2].strip()
        await add_channel(ch_id, title, url)
        await message.answer("✅ Канал успешно добавлен!", reply_markup=admin_main_kb())
        await state.clear()
    except Exception:
        await message.answer("❌ Ошибка формата. Попробуйте снова или вернитесь назад:", reply_markup=admin_back_kb())


# --- УПРАВЛЕНИЕ ПРОКСИ ---
@router.callback_query(F.data == "admin_proxies")
async def show_proxies(callback: types.CallbackQuery):
    await callback.message.edit_text("⏳ <i>Проверяю пинг всех прокси...</i>")

    proxies = await get_all_proxies()
    proxies_with_ping = []

    # Асинхронно проверяем пинг для всех прокси
    for proxy in proxies:
        ping = await ping_proxy(proxy.url, proxy.port)
        proxies_with_ping.append((proxy.id, proxy.url, ping))

    await callback.message.edit_text(
        "🌐 <b>Управление прокси</b>\nНажмите на прокси, чтобы удалить его:",
        reply_markup=admin_proxies_kb(proxies_with_ping)
    )


@router.callback_query(F.data.startswith("del_prx_"))
async def del_proxy_handler(callback: types.CallbackQuery):
    prx_id = int(callback.data.split("_")[2])
    await delete_proxy_db(prx_id)
    await callback.answer("✅ Прокси удален!")
    await show_proxies(callback)


@router.callback_query(F.data == "add_proxy")
async def add_proxy_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "➕ <b>Добавление прокси</b>\nОтправьте ссылку на прокси (например: <code>http://log:pass@ip:port</code>):",
        reply_markup=admin_back_kb())
    await state.set_state(AdminState.add_proxy)


@router.message(AdminState.add_proxy)
async def process_add_proxy(message: types.Message, state: FSMContext):
    url = message.text.strip()

    # Визуальный фидбек для админа
    msg = await message.answer("⏳ <i>Проверяю прокси перед добавлением...</i>")

    # Пингуем!
    ping = await ping_proxy(url)

    if ping is None:
        await msg.edit_text(
            "❌ <b>Прокси недоступен, мертв или имеет неверный формат!</b>\n\n"
            "Я не буду добавлять его в базу. Отправьте рабочую ссылку или вернитесь назад:",
            reply_markup=admin_back_kb()
        )
        return

    # Если пинг прошел успешно, добавляем в базу
    await add_proxy(url)

    await msg.edit_text(
        f"✅ <b>Прокси успешно добавлен!</b>\n"
        f"Пинг: <b>{ping} мс</b> 🟢",
        reply_markup=admin_main_kb()
    )
    await state.clear()


# --- РАССЫЛКА ---
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📣 Отправьте сообщение для рассылки (можно с фото/видео):",
                                     reply_markup=admin_back_kb())
    await state.set_state(AdminState.broadcast)


@router.message(AdminState.broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    users = await get_all_users()
    succ = 0
    await message.answer(f"⏳ Рассылка запущена для {len(users)} пользователей...")

    for user in users:
        try:
            await message.send_copy(chat_id=user.tg_id)
            succ += 1
            await asyncio.sleep(0.05)  # Защита от спам-блока Telegram
        except Exception:
            pass  # Юзер заблокировал бота

    await message.answer(f"✅ Рассылка завершена!\nУспешно доставлено: {succ} из {len(users)}.",
                         reply_markup=admin_main_kb())
    await state.clear()