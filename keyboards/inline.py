import urllib

from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.i18n import t


# ── Admin keyboards (не переводим) ──────────────────────────────────────────

def get_subscription_keyboard(channels: list, lang: str = 'ru'):
    builder = InlineKeyboardBuilder()
    for channel in channels:
        builder.row(
            types.InlineKeyboardButton(text=channel.title, url=channel.url)
        )
    builder.row(
        types.InlineKeyboardButton(
            text=t('btn_check_subscription', lang),
            callback_data="check_subscription",
            style="success"
        )
    )
    return builder.as_markup()


def admin_main_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📣 Рассылка", callback_data="admin_broadcast"),
        types.InlineKeyboardButton(text="📢 Каналы", callback_data="admin_channels")
    )
    builder.row(
        types.InlineKeyboardButton(text="🔗 Рекламные ссылки", callback_data="admin_refs_0")
    )
    builder.row(
        types.InlineKeyboardButton(text="⚙️ Настройки цен (⭐️)", callback_data="admin_prices")
    )
    return builder.as_markup()


def admin_back_kb():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔙 Назад в меню", callback_data="admin_main"))
    return builder.as_markup()


def get_admin_prices_kb(settings):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=f"Слот: {settings.price_slot}⭐️", callback_data="edit_price_slot"))
    builder.row(types.InlineKeyboardButton(text=f"ОП 7 дней: {settings.price_sponsor_7}⭐️", callback_data="edit_price_sponsor_7"))
    builder.row(types.InlineKeyboardButton(text=f"ОП 30 дней: {settings.price_sponsor_30}⭐️", callback_data="edit_price_sponsor_30"))
    builder.row(types.InlineKeyboardButton(text=f"Буст: {settings.price_boost}⭐️", callback_data="edit_price_boost"))
    builder.row(types.InlineKeyboardButton(text="🔙 Назад в Админку", callback_data="admin_main"))
    builder.adjust(1)
    return builder.as_markup()


def get_refs_pagination_kb(page: int, total_pages: int):
    builder = InlineKeyboardBuilder()
    nav_buttons = []
    if page > 0:
        nav_buttons.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"admin_refs_{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(types.InlineKeyboardButton(text="➡️", callback_data=f"admin_refs_{page + 1}"))
    if nav_buttons:
        builder.row(*nav_buttons)
    builder.row(types.InlineKeyboardButton(text="🔙 Назад в Админку", callback_data="admin_main"))
    return builder.as_markup()


def admin_channels_kb(channels):
    builder = InlineKeyboardBuilder()
    for ch in channels:
        builder.row(types.InlineKeyboardButton(text=f"❌ Удал: {ch.title}", callback_data=f"del_ch_{ch.id}", style="danger"))
    builder.row(types.InlineKeyboardButton(text="➕ Добавить канал", callback_data="add_channel", style="success"))
    builder.row(types.InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main"))
    return builder.as_markup()


# ── User keyboards ───────────────────────────────────────────────────────────

def get_proxy_control_keyboard(current_proxy_id: int, lang: str = 'ru'):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text=t('btn_other_proxy', lang),
            callback_data=f"replace_proxy_{current_proxy_id}"
        )
    )
    return builder.as_markup()


def get_proxy_vote_keyboard(proxy_id: int, url: str, likes: int, dislikes: int,
                            bot_username: str, lang: str = 'ru'):
    builder = InlineKeyboardBuilder()

    builder.row(types.InlineKeyboardButton(text=t('btn_connect', lang), url=url, style="success"))

    share_url = f"https://t.me/{bot_username}?start=prx_{proxy_id}"
    share_text = t('proxy_card_share_text', lang)
    encoded_text = urllib.parse.quote(share_text)
    tg_share_link = f"https://t.me/share/url?url={encoded_text}&text={share_url}"

    builder.row(types.InlineKeyboardButton(text=t('btn_share', lang), url=tg_share_link, style="primary"))

    builder.row(
        types.InlineKeyboardButton(text=f"👍 {likes}", callback_data=f"vote_{proxy_id}_up"),
        types.InlineKeyboardButton(text=f"👎 {dislikes}", callback_data=f"vote_{proxy_id}_down")
    )

    builder.row(types.InlineKeyboardButton(
        text=t('btn_no_connect', lang),
        callback_data=f"no_connect_{proxy_id}"
    ))

    return builder.as_markup()


def get_cabinet_main_keyboard(lang: str = 'ru'):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text=t('btn_favorites', lang), callback_data="liked_proxies_list", style="primary"))
    builder.row(types.InlineKeyboardButton(text=t('btn_partner_panel', lang), callback_data="my_proxies"))
    builder.row(types.InlineKeyboardButton(text=t('btn_language', lang), callback_data="open_language"))
    return builder.as_markup()


def get_liked_proxies_keyboard(proxies, lang: str = 'ru'):
    builder = InlineKeyboardBuilder()
    for p in proxies:
        host = p.url.split("server=")[1].split("&")[0] if "server=" in p.url else t('proxy_card_hidden_host', lang)
        builder.row(types.InlineKeyboardButton(text=f"🟢 #{p.id} | {host}", callback_data=f"show_liked_prx_{p.id}"))
    builder.row(types.InlineKeyboardButton(text=t('btn_back_to_cabinet', lang), callback_data="back_to_cabinet"))
    return builder.as_markup()


def get_my_proxies_keyboard(proxies, lang: str = 'ru'):
    builder = InlineKeyboardBuilder()
    for proxy in proxies:
        status = "🟢" if proxy.is_active else "🔴"
        host = proxy.url.split("server=")[1].split("&")[0] if "server=" in proxy.url else t('proxy_card_hidden_host', lang)
        builder.row(types.InlineKeyboardButton(
            text=f"{status} #{proxy.id} | {host}",
            callback_data=f"proxy_manage_{proxy.id}"
        ))
    builder.row(types.InlineKeyboardButton(text=t('btn_add_proxy', lang), callback_data="user_add_proxy"))
    builder.row(types.InlineKeyboardButton(text=t('btn_back_to_cabinet', lang), callback_data="back_to_cabinet"))
    return builder.as_markup()


def get_proxy_manage_keyboard(proxy_id: int, has_sponsor: bool = False, is_public: bool = True,
                              is_boosted: bool = False, lang: str = 'ru'):
    builder = InlineKeyboardBuilder()

    if is_boosted:
        builder.button(text=t('btn_boost_extend', lang), callback_data=f"buy_boost_{proxy_id}", style="success")
    else:
        builder.button(text=t('btn_boost', lang), callback_data=f"buy_boost_{proxy_id}", style="success")

    if has_sponsor:
        builder.button(text=t('btn_manage_op', lang), callback_data=f"manage_sponsor_{proxy_id}")
    else:
        builder.button(text=t('btn_buy_op', lang), callback_data=f"sponsor_menu_{proxy_id}", style="success")

    builder.button(
        text=t('visibility_yes' if is_public else 'visibility_no', lang),
        callback_data=f"toggle_public_{proxy_id}"
    )
    builder.button(text=t('btn_delete', lang), callback_data=f"user_delete_prx_{proxy_id}", style="danger")
    builder.button(text=t('btn_back_to_list', lang), callback_data="my_proxies")

    builder.adjust(1, 1, 2, 1)
    return builder.as_markup()


def get_limit_reached_keyboard(price_slot, lang: str = 'ru'):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text=t('btn_buy_slot', lang, price=price_slot),
        callback_data="buy_slot",
        style="success"
    ))
    builder.row(types.InlineKeyboardButton(text=t('btn_back', lang), callback_data="my_proxies"))
    return builder.as_markup()


def get_sponsor_tariffs_keyboard(proxy_id: int, price_sponsor_7, price_sponsor_30, lang: str = 'ru'):
    builder = InlineKeyboardBuilder()
    builder.button(text=t('btn_sponsor_7', lang, price=price_sponsor_7), callback_data=f"buy_sponsor_{proxy_id}_7",
                   style="primary")
    builder.button(text=t('btn_sponsor_30', lang, price=price_sponsor_30), callback_data=f"buy_sponsor_{proxy_id}_30",
                   style="success")
    builder.button(text=t('btn_cancel', lang), callback_data=f"proxy_manage_{proxy_id}")
    builder.adjust(1, 1, 1)
    return builder.as_markup()
