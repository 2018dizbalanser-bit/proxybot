from aiogram import Router, F, types, Bot
from datetime import datetime, timedelta
from sqlalchemy import select

from database.models import Proxy, User
from database.connect import async_session
from database.requests.get import add_transaction
from utils.i18n import t

router = Router()


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: types.Message, bot: Bot, lang: str):
    payload = message.successful_payment.invoice_payload
    amount = message.successful_payment.total_amount
    user_id = message.from_user.id

    if payload.startswith("sponsor_"):
        await process_sponsor_payment(message, bot, payload, lang)
        await add_transaction(user_id, amount, "sponsor")
    elif payload.startswith("slot_"):
        await process_slot_payment(message, payload, lang)
        await add_transaction(user_id, amount, "slot")
    elif payload.startswith("boost_"):
        await process_boost_payment(message, payload, lang)
        await add_transaction(user_id, amount, "boost")


async def process_slot_payment(message: types.Message, payload: str, lang: str = 'ru'):
    user_id = message.from_user.id

    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == user_id))
        user = result.scalar_one_or_none()

        if user:
            current_limit = user.proxy_limit if user.proxy_limit is not None else 3
            user.proxy_limit = current_limit + 1
            new_limit = user.proxy_limit
            await session.commit()
        else:
            new_user = User(tg_id=user_id, proxy_limit=4)
            session.add(new_user)
            await session.commit()
            new_limit = 4

    await message.answer(t('payment_slot_success', lang, limit=new_limit))


async def process_sponsor_payment(message: types.Message, bot: Bot, payload: str, lang: str = 'ru'):
    parts = payload.split("_")
    proxy_id = int(parts[1])
    channel_id = int(parts[2])
    days = int(parts[3])

    invite_link = await bot.export_chat_invite_link(channel_id)
    until_date = datetime.utcnow() + timedelta(days=days)

    async with async_session() as session:
        proxy = await session.get(Proxy, proxy_id)
        if proxy:
            proxy.sponsor_channel_id = channel_id
            proxy.sponsor_channel_url = invite_link
            proxy.sponsor_until = until_date
            await session.commit()

    await message.answer(
        t('payment_sponsor_success', lang,
          proxy_id=proxy_id,
          days=days,
          until=until_date.strftime('%d.%m.%Y %H:%M'))
    )


async def process_boost_payment(message: types.Message, payload: str, lang: str = 'ru'):
    proxy_id = int(payload.split("_")[1])

    async with async_session() as session:
        proxy = await session.get(Proxy, proxy_id)
        if proxy:
            now = datetime.utcnow()
            start_time = proxy.boost_until if (proxy.boost_until and proxy.boost_until > now) else now
            proxy.boost_until = start_time + timedelta(hours=24)
            new_date = proxy.boost_until
            await session.commit()

    await message.answer(
        t('payment_boost_success', lang,
          proxy_id=proxy_id,
          until=new_date.strftime('%d.%m %H:%M'))
    )
