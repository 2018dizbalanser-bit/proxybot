from aiogram import Router, F, types, Bot
from datetime import datetime, timedelta

from sqlalchemy import select

from database.models import Proxy, User
from database.connect import async_session
from database.requests.get import add_transaction

router = Router()


# --- 1. Универсальный ответ на ВСЕ предварительные запросы оплаты ---
@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


# --- Универсальный приемщик ВСЕХ успешных платежей ---
@router.message(F.successful_payment)
async def successful_payment_handler(message: types.Message, bot: Bot):
    payload = message.successful_payment.invoice_payload
    amount = message.successful_payment.total_amount
    user_id = message.from_user.id

    if payload.startswith("sponsor_"):
        await process_sponsor_payment(message, bot, payload)
        # Записываем в аналитику (определяем 7 или 30 дней по сумме или пейлоаду)
        # Для простоты можно писать просто 'sponsor'
        await add_transaction(user_id, amount, "sponsor")

    elif payload.startswith("slot_"):
        await process_slot_payment(message, payload)
        await add_transaction(user_id, amount, "slot")

    # ВОТ ЭТОТ БЛОК НУЖНО ДОБАВИТЬ:
    elif payload.startswith("boost_"):
        await process_boost_payment(message, payload)
        await add_transaction(user_id, amount, "boost")


# --- Логика начисления СЛОТА ---
async def process_slot_payment(message: types.Message, payload: str):
    # Берем ID напрямую у того, кто совершил платеж (это 100% надежно)
    user_id = message.from_user.id

    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == user_id))
        user = result.scalar_one_or_none()

        if user:
            # ЗАЩИТА ОТ NULL: Если в базе пустота, считаем что было 3
            current_limit = user.proxy_limit if user.proxy_limit is not None else 3
            user.proxy_limit = current_limit + 1
            new_limit = user.proxy_limit
            await session.commit()
        else:
            # На случай полтергейста: если юзера нет, создаем его сразу с 4 слотами
            new_user = User(tg_id=user_id, proxy_limit=4)
            session.add(new_user)
            await session.commit()
            new_limit = 4

    await message.answer(
        f"🎉 <b>Оплата успешно прошла!</b>\n\n"
        f"Ваш лимит прокси-серверов увеличен.\n"
        f"Теперь вы можете добавить до <b>{new_limit}</b> серверов!\n\n"
        f"Перейдите в «👤 Личный кабинет» -> «🌐 Мои прокси», чтобы добавить новый сервер."
    )


# --- 3. Логика начисления Спонсора ---
async def process_sponsor_payment(message: types.Message, bot: Bot, payload: str):
    parts = payload.split("_")
    proxy_id = int(parts[1])
    channel_id = int(parts[2])
    # Достаем дни из payload
    days = int(parts[3])

    invite_link = await bot.export_chat_invite_link(channel_id)
    # Прибавляем динамическое количество дней!
    until_date = datetime.utcnow() + timedelta(days=days)

    async with async_session() as session:
        proxy = await session.get(Proxy, proxy_id)
        if proxy:
            proxy.sponsor_channel_id = channel_id
            proxy.sponsor_channel_url = invite_link
            proxy.sponsor_until = until_date
            await session.commit()

    await message.answer(
        f"🎉 <b>Оплата успешно прошла!</b>\n\n"
        f"Канал привязан к прокси <b>#{proxy_id}</b> на <b>{days} дней</b> (до <code>{until_date.strftime('%d.%m.%Y %H:%M')}</code>).\n\n"
        f"Теперь скопируйте вашу реферальную ссылку в Личном кабинете и продвигайте её. "
        f"Все перешедшие по ней будут обязаны подписаться на ваш канал!"
    )


# Добавь в payments.py функцию:

async def process_boost_payment(message: types.Message, payload: str):
    proxy_id = int(payload.split("_")[1])

    async with async_session() as session:
        proxy = await session.get(Proxy, proxy_id)
        if proxy:
            now = datetime.utcnow()
            # Если буст еще действует, продлеваем его. Если нет - стартуем с текущего момента.
            start_time = proxy.boost_until if (proxy.boost_until and proxy.boost_until > now) else now
            proxy.boost_until = start_time + timedelta(hours=24)
            new_date = proxy.boost_until
            await session.commit()

    await message.answer(
        f"🚀 <b>Буст активирован!</b>\n\n"
        f"Прокси <b>#{proxy_id}</b> поднят в категорию VIP до <code>{new_date.strftime('%d.%m %H:%M')}</code>.\n"
        f"Теперь пользователи будут видеть его в первую очередь!"
    )