from aiogram import Router, F, types, Bot
from datetime import datetime, timedelta

from database.models import Proxy
from database.connect import async_session

router = Router()


# --- 1. Универсальный ответ на ВСЕ предварительные запросы оплаты ---
@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


# --- 2. Универсальный приемщик ВСЕХ успешных платежей ---
@router.message(F.successful_payment)
async def successful_payment_handler(message: types.Message, bot: Bot):
    payload = message.successful_payment.invoice_payload

    # Роутер (маршрутизатор) платежей по payload
    if payload.startswith("sponsor_"):
        await process_sponsor_payment(message, bot, payload)

    elif payload.startswith("slots_"):
        pass  # Заглушка для будущей покупки слотов

    elif payload.startswith("boost_"):
        pass  # Заглушка для будущего буста


# --- 3. Логика начисления Спонсора ---
async def process_sponsor_payment(message: types.Message, bot: Bot, payload: str):
    parts = payload.split("_")
    proxy_id = int(parts[1])
    channel_id = int(parts[2])

    # Бот генерирует ссылку-приглашение в канал
    invite_link = await bot.export_chat_invite_link(channel_id)
    until_date = datetime.utcnow() + timedelta(days=7)

    async with async_session() as session:
        proxy = await session.get(Proxy, proxy_id)
        if proxy:
            proxy.sponsor_channel_id = channel_id
            proxy.sponsor_channel_url = invite_link
            proxy.sponsor_until = until_date
            await session.commit()

    await message.answer(
        f"🎉 <b>Оплата успешно прошла!</b>\n\n"
        f"Канал привязан к прокси <b>#{proxy_id}</b> до <code>{until_date.strftime('%d.%m.%Y %H:%M')}</code>.\n\n"
        f"Теперь скопируйте вашу реферальную ссылку в Личном кабинете и продвигайте её. "
        f"Все перешедшие по ней будут обязаны подписаться на ваш канал!"
    )