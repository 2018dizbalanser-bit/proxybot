import asyncio
from datetime import datetime
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import types

from database.connect import async_session
from database.models import Proxy
from sqlalchemy import select
from utils.ping import ping_proxy, parse_proxy_url


# Оставляем функцию уведомлений
async def notify_owner(bot: Bot, owner_id: int | None, text: str, reply_markup=None):
    if not owner_id:
        return
    try:
        await bot.send_message(
            chat_id=owner_id,
            text=text,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    except Exception:
        pass


# --- НОВАЯ ОПТИМИЗИРОВАННАЯ ФУНКЦИЯ ПИНГА ДЛЯ ОДНОГО ПРОКСИ ---
async def _ping_task(proxy_id: int, host: str, port: int, semaphore: asyncio.Semaphore):
    """Выполняет пинг с ограничением одновременных подключений (семафором)"""
    async with semaphore:
        is_alive, resp_time = await ping_proxy(host, port)
        return proxy_id, is_alive, resp_time


# --- ГЛАВНЫЙ ВОРКЕР ---
async def background_proxy_checker(bot: Bot):
    """Фоновый воркер для проверки прокси-серверов (High-Performance)"""

    # Храним страйки в оперативной памяти
    proxy_strikes = {}

    # Ограничиваем одновременные пинги до 50 штук.
    # Это спасет твой 1-ядерный сервер от перегрузки по сокетам.
    concurrency_limit = 50
    semaphore = asyncio.Semaphore(concurrency_limit)

    while True:
        try:
            async with async_session() as session:
                result = await session.execute(select(Proxy))
                proxies = result.scalars().all()

                # 1. Быстрая синхронная проверка спонсоров
                for proxy in proxies:
                    if proxy.sponsor_until and proxy.sponsor_until < datetime.utcnow():
                        proxy_id = proxy.id
                        owner_id = proxy.owner_id

                        proxy.sponsor_channel_id = None
                        proxy.sponsor_channel_url = None
                        proxy.sponsor_until = None

                        if owner_id:
                            markup = InlineKeyboardBuilder().row(
                                types.InlineKeyboardButton(
                                    text="📢 Продлить ОП",
                                    callback_data=f"sponsor_menu_{proxy_id}"  # Изменили тут!
                                )
                            ).as_markup()

                            text = (
                                f"🔔 <b>Срок Обязательной Подписки истек!</b>\n\n"
                                f"Привязка канала к вашему прокси <b>#{proxy_id}</b> завершена. "
                                f"Люди больше не обязаны подписываться на ваш канал при получении прокси.\n\n"
                                f"👇 Нажмите кнопку ниже, чтобы возобновить конверсию трафика:"
                            )
                            # Запускаем уведомление фоном, чтобы не тормозить цикл
                            asyncio.create_task(notify_owner(bot, owner_id, text, reply_markup=markup))

                # 2. Формируем задачи для конкурентного пинга
                ping_tasks = []
                for proxy in proxies:
                    host, port = parse_proxy_url(proxy.url)
                    if host and port:
                        ping_tasks.append(_ping_task(proxy.id, host, port, semaphore))

                # Запускаем все пинги одновременно (пачками по 50) и ждем результатов
                ping_results = await asyncio.gather(*ping_tasks)

                # Превращаем результаты в словарь для быстрого поиска {proxy_id: (is_alive, resp_time)}
                ping_dict = {res[0]: (res[1], res[2]) for res in ping_results}

                # 3. Применяем результаты пингов к базе данных
                for proxy in proxies:
                    if proxy.id not in ping_dict:
                        continue

                    is_alive, resp_time = ping_dict[proxy.id]
                    was_active = proxy.is_active

                    if is_alive:
                        # УСПЕХ: Обнуляем страйки
                        proxy_strikes[proxy.id] = 0

                        proxy.is_active = True
                        proxy.success_checks += 1
                        proxy.total_checks += 1

                        # Обновляем скор (чем меньше время ответа, тем лучше скор)
                        # Формула: Рейтинг = Лайки - Дизлайки - (Время_ответа / 100)
                        proxy.score = float(proxy.likes - proxy.dislikes - (resp_time / 100.0))

                    else:
                        # ПРОВАЛ: Начисляем страйк
                        current_strikes = proxy_strikes.get(proxy.id, 0) + 1
                        proxy_strikes[proxy.id] = current_strikes
                        proxy.total_checks += 1

                        # Правило 3-х страйков
                        if current_strikes >= 3:
                            proxy.is_active = False
                            proxy.score = 9999.0

                            # Уведомляем только 1 раз при падении
                            if was_active:
                                short_url = proxy.url.split('@')[-1] if '@' in proxy.url else proxy.url
                                alert_text = (
                                    f"🚨 <b>Ваш прокси перестал работать!</b>\n\n"
                                    f"💀 Он не отвечает на запросы (3 попытки подряд) и временно исключен из выдачи:\n"
                                    f"🌐 <code>{short_url}</code>\n\n"
                                    f"🔧 <i>Пожалуйста, проверьте работу сервера.</i>"
                                )
                                asyncio.create_task(notify_owner(bot, proxy.owner_id, alert_text))

                # Сохраняем все изменения в БД одним махом
                await session.commit()

        except Exception as e:
            print(f"Ошибка в рокере: {e}")

        # Спим 3 минуты до следующей проверки
        await asyncio.sleep(180)