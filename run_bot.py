import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from data.config import BOT_TOKEN
from handlers.users import setup_users_routers
from handlers.admins import setup_admin_routers
from utils.worker import background_proxy_checker
from middleware.i18n import i18n_middleware


async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='html'))

    dp = Dispatcher()

    dp.update.outer_middleware(i18n_middleware)

    dp.include_routers(
        setup_admin_routers(),
        setup_users_routers()
    )

    asyncio.create_task(background_proxy_checker(bot))

    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Бот выключен')
