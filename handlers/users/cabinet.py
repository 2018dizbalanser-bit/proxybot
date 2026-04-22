from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from database.models import Proxy
from database.connect import async_session
from database.requests.get import get_user_proxies, get_proxy_by_id, get_user, get_user_liked_proxies, \
    get_user_stats_for_cabinet, get_bot_settings
from database.requests.delete import delete_proxy_db
from keyboards.inline import get_cabinet_main_keyboard, get_my_proxies_keyboard, get_proxy_manage_keyboard, \
    get_limit_reached_keyboard, get_sponsor_tariffs_keyboard, get_liked_proxies_keyboard
from utils.i18n import t, all_values
from utils.ping import ping_proxy, parse_proxy_url

router = Router()


class AddProxyState(StatesGroup):
    waiting_for_url = State()


class SponsorState(StatesGroup):
    waiting_for_forward = State()


async def _render_main_cabinet(user: types.User, send_method, lang: str = 'ru'):
    stats = await get_user_stats_for_cabinet(user.id)

    text = t('cabinet_title', lang)
    text += (f"<tg-emoji emoji-id='5974526806995242353'>👍</tg-emoji> "
             f"ID: <code>{user.id}</code>\n\n")
    text += (f"<tg-emoji emoji-id='5974310710010711597'>👍</tg-emoji> "
             + t('cabinet_activity', lang, viewed=stats['viewed'], liked=stats['liked']))

    if stats['added'] > 0:
        text += (f"<tg-emoji emoji-id='5974104203688152439'>👍</tg-emoji> "
                 + t('cabinet_added_servers', lang, added=stats['added']))

    text += t('cabinet_hints', lang)

    await send_method(text, reply_markup=get_cabinet_main_keyboard(lang))


@router.message(F.text.in_(all_values('btn_cabinet')))
async def show_cabinet_msg(message: types.Message, lang: str):
    await _render_main_cabinet(message.from_user, message.answer, lang)


@router.callback_query(F.data == "back_to_cabinet")
async def back_to_cabinet_call(callback: types.CallbackQuery, state: FSMContext, lang: str):
    await state.clear()
    await _render_main_cabinet(callback.from_user, callback.message.edit_text, lang)
    await callback.answer()


@router.callback_query(F.data == "liked_proxies_list")
async def show_liked_proxies_handler(callback: types.CallbackQuery, lang: str):
    proxies = await get_user_liked_proxies(callback.from_user.id)

    if not proxies:
        markup = InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text=t('btn_back_to_cabinet', lang), callback_data="back_to_cabinet")
        ).as_markup()
        await callback.message.edit_text(t('favorites_title', lang), reply_markup=markup)
        return

    await callback.message.edit_text(
        t('favorites_list', lang),
        reply_markup=get_liked_proxies_keyboard(proxies, lang)
    )


@router.callback_query(F.data.startswith("show_liked_prx_"))
async def show_specific_liked_proxy(callback: types.CallbackQuery, bot: Bot, lang: str):
    proxy_id = int(callback.data.split("_")[3])
    proxy = await get_proxy_by_id(proxy_id)

    if not proxy or not proxy.is_active:
        await callback.answer(t('server_unavailable', lang), show_alert=True)
        return

    uptime = round((proxy.success_checks / proxy.total_checks) * 100, 1) if proxy.total_checks > 0 else 100
    host = proxy.url.split("server=")[1].split("&")[0] if "server=" in proxy.url else t('proxy_card_hidden_host', lang)

    text = t('favorite_proxy_card', lang, proxy_id=proxy.id, host=host, uptime=uptime)

    markup = InlineKeyboardBuilder()
    markup.row(types.InlineKeyboardButton(text=t('btn_connect', lang), url=proxy.url))
    markup.row(types.InlineKeyboardButton(text=t('btn_back_to_list', lang), callback_data="liked_proxies_list"))

    await callback.message.edit_text(text, reply_markup=markup.as_markup(), disable_web_page_preview=True)


@router.callback_query(F.data == "my_proxies")
async def show_my_proxies_call(callback: types.CallbackQuery, lang: str):
    user_id = callback.from_user.id
    proxies = await get_user_proxies(user_id)
    user = await get_user(user_id)
    user_limit = user.proxy_limit if (user and user.proxy_limit is not None) else 3

    text = t('my_proxies_title', lang, count=len(proxies), limit=user_limit)
    text += t('my_proxies_empty', lang) if not proxies else t('my_proxies_hint', lang)

    await callback.message.edit_text(text, reply_markup=get_my_proxies_keyboard(proxies, lang))


@router.callback_query(F.data.startswith("sponsor_menu_"))
async def sponsor_menu_handler(callback: types.CallbackQuery, lang: str):
    proxy_id = int(callback.data.split("_")[2])
    settings = await get_bot_settings()
    await callback.message.edit_text(
        t('sponsor_menu_text', lang),
        reply_markup=get_sponsor_tariffs_keyboard(
            proxy_id, settings.price_sponsor_7, settings.price_sponsor_30, lang
        )
    )


@router.callback_query(F.data.startswith("buy_sponsor_"))
async def start_buy_sponsor(callback: types.CallbackQuery, state: FSMContext, lang: str):
    parts = callback.data.split("_")
    proxy_id = int(parts[2])
    days = int(parts[3])

    await state.update_data(proxy_id=proxy_id, days=days)

    await callback.message.edit_text(
        t('sponsor_bind_prompt', lang, days=days),
        reply_markup=InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text=t('btn_cancel', lang), callback_data=f"sponsor_menu_{proxy_id}")
        ).as_markup()
    )
    await state.set_state(SponsorState.waiting_for_forward)


@router.message(SponsorState.waiting_for_forward)
async def process_sponsor_channel(message: types.Message, state: FSMContext, bot: Bot, lang: str):
    if not message.forward_from_chat or message.forward_from_chat.type != 'channel':
        await message.answer(t('sponsor_not_channel', lang))
        return

    channel_id = message.forward_from_chat.id
    channel_title = message.forward_from_chat.title

    try:
        chat_member = await bot.get_chat_member(channel_id, bot.id)
        if chat_member.status not in ['administrator', 'creator']:
            await message.answer(t('sponsor_not_admin', lang))
            return
    except Exception:
        await message.answer(t('sponsor_access_error', lang))
        return

    data = await state.get_data()
    proxy_id = data['proxy_id']
    days = data['days']

    settings = await get_bot_settings()
    amount = settings.price_sponsor_30 if days == 30 else settings.price_sponsor_7
    payload = f"sponsor_{proxy_id}_{channel_id}_{days}"

    prices = [types.LabeledPrice(label=t('invoice_sponsor_label', lang, days=days), amount=amount)]

    await message.answer_invoice(
        title=t('invoice_sponsor_title', lang),
        description=t('invoice_sponsor_desc', lang, channel_title=channel_title, proxy_id=proxy_id, days=days),
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=prices
    )
    await state.clear()


@router.callback_query(F.data.in_(["buy_vip"]))
async def future_features_stub(callback: types.CallbackQuery, lang: str):
    await callback.answer(t('feature_wip', lang), show_alert=True)


@router.callback_query(F.data.startswith("proxy_manage_"))
async def manage_specific_proxy(callback: types.CallbackQuery, bot: Bot, lang: str):
    proxy_id = int(callback.data.split("_")[2])
    proxy = await get_proxy_by_id(proxy_id)

    if not proxy or proxy.owner_id != callback.from_user.id:
        return

    uptime = round((proxy.success_checks / proxy.total_checks) * 100, 1) if proxy.total_checks > 0 else 100
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=prx_{proxy.id}"

    has_sponsor = bool(proxy.sponsor_until and proxy.sponsor_until > datetime.utcnow())
    is_boosted = bool(proxy.boost_until and proxy.boost_until > datetime.utcnow())

    status = t('proxy_status_active', lang) if proxy.is_active else t('proxy_status_dead', lang)

    text = t('proxy_manage_text', lang,
             proxy_id=proxy.id,
             url=proxy.url,
             status=status,
             uptime=uptime,
             score=round(proxy.score, 1),
             likes=proxy.likes,
             dislikes=proxy.dislikes)

    if is_boosted:
        text += t('proxy_manage_boost_active', lang, until=proxy.boost_until.strftime('%d.%m %H:%M'))

    if has_sponsor:
        text += t('proxy_manage_op_active', lang, until=proxy.sponsor_until.strftime('%d.%m %H:%M'))

    text += t('proxy_manage_reflink', lang, ref_link=ref_link)

    await callback.message.edit_text(
        text,
        reply_markup=get_proxy_manage_keyboard(proxy.id, has_sponsor, proxy.is_public, is_boosted, lang),
        disable_web_page_preview=True
    )


@router.callback_query(F.data.startswith("user_delete_prx_"))
async def delete_user_proxy(callback: types.CallbackQuery, lang: str):
    proxy_id = int(callback.data.split("_")[3])
    proxy = await get_proxy_by_id(proxy_id)

    if proxy and proxy.owner_id == callback.from_user.id:
        await delete_proxy_db(proxy_id)
        await callback.answer(t('delete_proxy_success', lang), show_alert=True)
    else:
        await callback.answer(t('delete_proxy_error', lang), show_alert=True)

    await _render_main_cabinet(callback.from_user, callback.message.edit_text, lang)


@router.callback_query(F.data == "user_add_proxy")
async def start_add_proxy(callback: types.CallbackQuery, state: FSMContext, lang: str):
    user_id = callback.from_user.id
    proxies = await get_user_proxies(user_id)
    user = await get_user(user_id)
    user_limit = user.proxy_limit if (user and user.proxy_limit is not None) else 3
    settings = await get_bot_settings()

    if len(proxies) >= user_limit:
        await callback.message.edit_text(
            t('limit_reached', lang, limit=user_limit, price=settings.price_slot),
            reply_markup=get_limit_reached_keyboard(settings.price_slot, lang)
        )
        return

    await callback.message.edit_text(
        t('add_proxy_prompt', lang),
        reply_markup=InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text=t('btn_cancel', lang), callback_data="my_proxies")
        ).as_markup(),
        disable_web_page_preview=True
    )
    await state.set_state(AddProxyState.waiting_for_url)
    await callback.answer()


@router.callback_query(F.data == "buy_slot")
async def buy_slot_invoice(callback: types.CallbackQuery, bot: Bot, lang: str):
    settings = await get_bot_settings()
    prices = [types.LabeledPrice(label=t('invoice_slot_label', lang), amount=settings.price_slot)]

    await callback.message.answer_invoice(
        title=t('invoice_slot_title', lang),
        description=t('invoice_slot_desc', lang),
        payload=f"slot_{callback.from_user.id}",
        provider_token="",
        currency="XTR",
        prices=prices
    )
    await callback.answer()


@router.message(AddProxyState.waiting_for_url)
async def process_proxy_url(message: types.Message, state: FSMContext, bot: Bot, lang: str):
    url = message.text.strip()

    if not (url.startswith("tg://proxy?server=") or url.startswith("https://t.me/proxy?server=")):
        await message.answer(t('add_proxy_bad_format', lang))
        return

    wait_msg = await message.answer(t('add_proxy_pinging', lang))

    host, port = parse_proxy_url(url)
    if not host or not port:
        await wait_msg.edit_text(t('add_proxy_bad_url', lang))
        return

    is_alive, resp_time = await ping_proxy(host, port)

    if not is_alive:
        await wait_msg.edit_text(t('add_proxy_dead', lang))
        return

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
                t('add_proxy_success', lang, ping=int(resp_time), ref_link=ref_link),
                reply_markup=InlineKeyboardBuilder().row(
                    types.InlineKeyboardButton(text=t('btn_to_cabinet', lang), callback_data="back_to_cabinet")
                ).as_markup(),
                disable_web_page_preview=True
            )
            await state.clear()

        except IntegrityError:
            await session.rollback()
            await wait_msg.edit_text(
                t('add_proxy_duplicate', lang),
                reply_markup=InlineKeyboardBuilder().row(
                    types.InlineKeyboardButton(text=t('btn_to_cabinet', lang), callback_data="back_to_cabinet")
                ).as_markup()
            )
            await state.clear()


@router.callback_query(F.data.startswith("manage_sponsor_"))
async def manage_sponsor_handler(callback: types.CallbackQuery, lang: str):
    proxy_id = int(callback.data.split("_")[2])
    proxy = await get_proxy_by_id(proxy_id)

    if not proxy or not proxy.sponsor_until or proxy.sponsor_until < datetime.utcnow():
        await callback.answer(t('sponsor_not_found', lang), show_alert=True)
        return

    text = t('sponsor_manage_text', lang,
             proxy_id=proxy_id,
             channel_url=proxy.sponsor_channel_url,
             until=proxy.sponsor_until.strftime('%d.%m.%Y %H:%M'))

    markup = InlineKeyboardBuilder()
    markup.row(
        types.InlineKeyboardButton(text="🗑 Отвязать канал", callback_data=f"unlink_sponsor_{proxy_id}", style="danger"))
    markup.row(types.InlineKeyboardButton(text="🔙 Назад к прокси", callback_data=f"proxy_manage_{proxy_id}"))

    await callback.message.edit_text(text, reply_markup=markup.as_markup(), disable_web_page_preview=True)


@router.callback_query(F.data.startswith("unlink_sponsor_"))
async def unlink_sponsor_handler(callback: types.CallbackQuery, lang: str):
    proxy_id = int(callback.data.split("_")[2])

    async with async_session() as session:
        proxy = await session.get(Proxy, proxy_id)
        if proxy and proxy.owner_id == callback.from_user.id:
            proxy.sponsor_channel_id = None
            proxy.sponsor_channel_url = None
            proxy.sponsor_until = None
            await session.commit()

    await callback.message.edit_text(
        t('sponsor_unlinked', lang),
        reply_markup=InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text=t('btn_back_to_proxy', lang), callback_data=f"proxy_manage_{proxy_id}")
        ).as_markup()
    )


@router.callback_query(F.data.startswith("toggle_public_"))
async def toggle_public_handler(callback: types.CallbackQuery, bot: Bot, lang: str):
    proxy_id = int(callback.data.split("_")[2])

    new_status = True
    async with async_session() as session:
        proxy = await session.get(Proxy, proxy_id)
        if proxy and proxy.owner_id == callback.from_user.id:
            proxy.is_public = not proxy.is_public
            new_status = proxy.is_public
            await session.commit()

    msg_key = 'visibility_on' if new_status else 'visibility_off'
    await callback.answer(t(msg_key, lang), show_alert=True)
    await manage_specific_proxy(callback, bot, lang)


@router.callback_query(F.data.startswith("buy_boost_"))
async def buy_boost_handler(callback: types.CallbackQuery, lang: str):
    proxy_id = int(callback.data.split("_")[2])
    settings = await get_bot_settings()

    prices = [types.LabeledPrice(label=t('invoice_boost_label', lang), amount=settings.price_boost)]

    await callback.message.answer_invoice(
        title=t('invoice_boost_title', lang),
        description=t('invoice_boost_desc', lang, proxy_id=proxy_id),
        payload=f"boost_{proxy_id}",
        provider_token="",
        currency="XTR",
        prices=prices
    )
    await callback.answer()
