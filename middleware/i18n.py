from aiogram.types import TelegramObject

from database.requests.get import get_user


async def i18n_middleware(handler, event: TelegramObject, data: dict):
    tg_user = data.get('event_from_user')
    lang = 'ru'

    if tg_user:
        db_user = await get_user(tg_user.id)
        if db_user and db_user.language:
            lang = db_user.language

    data['lang'] = lang
    return await handler(event, data)
