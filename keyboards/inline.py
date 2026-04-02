import urllib

from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from data.config import PRICE_SLOT, PRICE_SPONSOR_7_DAYS, PRICE_SPONSOR_30_DAYS
from utils.ping import parse_proxy_url


def get_subscription_keyboard(channels: list):
    builder = InlineKeyboardBuilder()

    # Динамически добавляем кнопки каналов
    for channel in channels:
        builder.row(
            types.InlineKeyboardButton(
                text=channel.title,
                url=channel.url
            )
        )

    # Кнопка проверки подписки
    builder.row(
        types.InlineKeyboardButton(
            text="✅ Проверить подписку",
            callback_data="check_subscription"
        )
    )

    return builder.as_markup()


def admin_main_kb():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📣 Рассылка", callback_data="admin_broadcast"))
    builder.row(types.InlineKeyboardButton(text="📢 Управление каналами", callback_data="admin_channels"))
    builder.row(types.InlineKeyboardButton(text="🌐 Управление прокси", callback_data="admin_proxies"))
    return builder.as_markup()


def admin_back_kb():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔙 Назад в меню", callback_data="admin_main"))
    return builder.as_markup()


def admin_channels_kb(channels):
    builder = InlineKeyboardBuilder()
    for ch in channels:
        # Кнопка с названием канала и крестиком для удаления
        builder.row(types.InlineKeyboardButton(text=f"❌ Удал: {ch.title}", callback_data=f"del_ch_{ch.id}"))

    builder.row(types.InlineKeyboardButton(text="➕ Добавить канал", callback_data="add_channel"))
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main"))
    return builder.as_markup()


def admin_proxies_kb(proxies_with_ping):
    builder = InlineKeyboardBuilder()
    for proxy_id, url, ping in proxies_with_ping:
        status = f"{ping} мс 🟢" if ping else "Мертв 🔴"

        # Теперь достаем IP и Порт новой железобетонной функцией
        host, port = parse_proxy_url(url)
        if host and port:
            display_name = f"{host}:{port}"  # Будет красиво, например 142.25.12.3:443
        else:
            display_name = url[:20] + "..."

        builder.row(types.InlineKeyboardButton(
            text=f"❌ {display_name} | {status}",
            callback_data=f"del_prx_{proxy_id}"
        ))

    builder.row(types.InlineKeyboardButton(text="➕ Добавить прокси", callback_data="add_proxy"))
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main"))
    return builder.as_markup()


def get_proxy_control_keyboard(current_proxy_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="🔄 Выдать другой прокси",
            callback_data=f"replace_proxy_{current_proxy_id}"
        )
    )
    return builder.as_markup()


def get_proxy_vote_keyboard(proxy_id: int, url: str, likes: int, dislikes: int, bot_username: str,
                            show_replace: bool = True):
    builder = InlineKeyboardBuilder()

    # 1-й ряд: Огромная CTA-кнопка подключения
    builder.row(types.InlineKeyboardButton(text="🚀 Подключиться", url=url))

    # 2-й ряд: Голосование (делим пополам)
    builder.row(
        types.InlineKeyboardButton(text=f"👍 {likes}", callback_data=f"vote_{proxy_id}_up"),
        types.InlineKeyboardButton(text=f"👎 {dislikes}", callback_data=f"vote_{proxy_id}_down")
    )

    # --- Генерируем ссылку для "Поделиться" ---
    share_url = f"https://t.me/{bot_username}?start=prx_{proxy_id}"
    # Красивый заготовленный текст, который отправится вместе со ссылкой:
    share_text = "🔥 Смотри, какой быстрый и бесплатный прокси я нашел! Подключайся в один клик 👇\n"
    # Кодируем текст, чтобы Telegram его понял
    encoded_text = urllib.parse.quote(share_text)
    tg_share_link = f"https://t.me/share/url?url={encoded_text}&text={share_url}"

    # 3-й ряд: Кнопки действий (Шер и Замена)
    action_row = [types.InlineKeyboardButton(text="🔗 Поделиться", url=tg_share_link)]
    if show_replace:
        action_row.append(types.InlineKeyboardButton(text="🔄 Другой прокси", callback_data=f"replace_proxy_{proxy_id}"))

    builder.row(*action_row)

    return builder.as_markup()


def get_cabinet_main_keyboard():
    """Главное меню личного кабинета"""
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⭐ Мои избранные прокси", callback_data="liked_proxies_list"))
    # Оставляем callback_data="my_proxies", так как на нем уже завязана логика владельца серверов
    builder.row(types.InlineKeyboardButton(text="⚙️ Панель партнера", callback_data="my_proxies"))
    return builder.as_markup()


def get_liked_proxies_keyboard(proxies):
    """Список лайкнутых прокси"""
    builder = InlineKeyboardBuilder()

    for p in proxies:
        host = p.url.split("server=")[1].split("&")[0] if "server=" in p.url else "Скрытый адрес"
        builder.row(types.InlineKeyboardButton(text=f"🟢 #{p.id} | {host}", callback_data=f"show_liked_prx_{p.id}"))

    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_cabinet"))
    return builder.as_markup()


def get_my_proxies_keyboard(proxies):
    """Клавиатура со списком прокси пользователя"""
    builder = InlineKeyboardBuilder()

    for proxy in proxies:
        status = "🟢" if proxy.is_active else "🔴"

        # Достаем IP или домен из MTProto ссылки
        host = "Скрытый адрес"
        if "server=" in proxy.url:
            # Парсим: берем всё что после server= и до следующего &
            host = proxy.url.split("server=")[1].split("&")[0]

        # Формируем красивый текст кнопки
        btn_text = f"{status} #{proxy.id} | {host}"

        builder.row(types.InlineKeyboardButton(
            text=btn_text,
            callback_data=f"proxy_manage_{proxy.id}"
        ))

    builder.row(types.InlineKeyboardButton(text="➕ Добавить прокси", callback_data="user_add_proxy"))
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_cabinet"))

    return builder.as_markup()


# Добавили is_boosted: bool = False
def get_proxy_manage_keyboard(proxy_id: int, has_sponsor: bool = False, is_public: bool = True,
                              is_boosted: bool = False):
    builder = InlineKeyboardBuilder()

    # МЕНЯЕМ КНОПКУ БУСТА В ЗАВИСИМОСТИ ОТ СТАТУСА
    if is_boosted:
        builder.button(text="🚀 Продлить Буст (+24ч)", callback_data=f"buy_boost_{proxy_id}")
    else:
        builder.button(text="🚀 Буст в ТОП", callback_data=f"buy_boost_{proxy_id}")

    # ... остальной код (спонсор, видимость, удаление, назад) ...
    if has_sponsor:
        builder.button(text="📢 Настройки ОП", callback_data=f"manage_sponsor_{proxy_id}")
    else:
        builder.button(text="📢 Купить ОП", callback_data=f"sponsor_menu_{proxy_id}")

    visibility_text = "👁 В каталоге: ДА" if is_public else "🚫 В каталоге: НЕТ"
    builder.button(text=visibility_text, callback_data=f"toggle_public_{proxy_id}")

    builder.button(text="🗑 Удалить", callback_data=f"user_delete_prx_{proxy_id}")
    builder.button(text="🔙 К списку", callback_data="my_proxies")

    builder.adjust(1, 1, 2, 1)
    return builder.as_markup()


def get_limit_reached_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=f"📦 Купить +1 слот ({PRICE_SLOT} ⭐️)", callback_data="buy_slot"))
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="my_proxies"))
    return builder.as_markup()


# Выбор тарифа ОП
def get_sponsor_tariffs_keyboard(proxy_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text=f"🗓 7 дней — {PRICE_SPONSOR_7_DAYS} ⭐️", callback_data=f"buy_sponsor_{proxy_id}_7")
    builder.button(text=f"🔥 30 дней — {PRICE_SPONSOR_30_DAYS} ⭐️ (Выгодно)", callback_data=f"buy_sponsor_{proxy_id}_30")
    builder.button(text="🔙 Отмена", callback_data=f"proxy_manage_{proxy_id}")
    builder.adjust(1, 1, 1)
    return builder.as_markup()