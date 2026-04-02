import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from data.config import BOT_TOKEN
# from database.connect import create_tables

# Позже мы раскомментируем эти импорты, когда напишем роутеры
from handlers.users import setup_users_routers
from handlers.admins import setup_admin_routers
from utils.worker import background_proxy_checker


async def main():
    # Создаем таблицы в БД при запуске
    # await create_tables()
    # print("База данных подключена и таблицы созданы.")

    # Инициализируем бота и диспетчер
    # bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='html'), proxy="socks5://72.49.49.11:31034")
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='html'))

    dp = Dispatcher()

    # Подключаем роутеры (раскомментируем позже)
    dp.include_routers(
        setup_admin_routers(),
        setup_users_routers()
    )

    # Запускаем фоновый чекер (он не блокирует работу бота!)
    asyncio.create_task(background_proxy_checker(bot))

    # Пропускаем старые апдейты и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Бот выключен')