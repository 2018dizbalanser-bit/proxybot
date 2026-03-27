import asyncio
from aiogram import Bot
from sqlalchemy import select

from database.connect import async_session
from database.models import Proxy
from utils.ping import ping_proxy
from data.config import ADMIN_IDS


async def notify_admins(bot: Bot, text: str):
    """Рассылает экстренное сообщение всем админам из конфига"""
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, disable_web_page_preview=True)
        except Exception:
            pass  # Админ мог заблокировать бота, игнорируем


async def background_proxy_checker(bot: Bot):
    """Фоновая задача для проверки всех прокси каждые 3 минуты с алертами"""
    while True:
        async with async_session() as session:
            result = await session.scalars(select(Proxy))
            proxies = result.all()

            for proxy in proxies:
                # Запоминаем состояние ДО проверки
                was_active = proxy.is_active
                old_score = proxy.score

                # Пингуем
                tcp_ping, resp_time = await ping_proxy(proxy.url)

                proxy.total_checks += 1

                if tcp_ping is not None and resp_time is not None:
                    proxy.success_checks += 1
                    proxy.is_active = True
                    new_score = (tcp_ping * 0.3) + (resp_time * 0.7)
                    proxy.score = new_score

                    # АЛЕРТ 1: Сильная деградация (если раньше пинг был норм, а стал > 1500 мс)
                    if old_score < 1500 and new_score >= 1500:
                        short_url = proxy.url.split('@')[-1] if '@' in proxy.url else proxy.url
                        await notify_admins(
                            bot,
                            f"⚠️ <b>Внимание! Деградация прокси!</b>\n\n"
                            f"🌐 <code>{short_url}</code>\n\n"
                            f"📉 Скорость отклика упала до <b>{round(new_score, 1)} мс</b>.\n"
                            f"<i>Сервер сильно перегружен, возможно, стоит его проверить.</i>"
                        )
                else:
                    proxy.is_active = False
                    proxy.score = 9999.0

                    # АЛЕРТ 2: Прокси отвалился (был активен, а теперь нет)
                    if was_active:
                        short_url = proxy.url.split('@')[-1] if '@' in proxy.url else proxy.url
                        await notify_admins(
                            bot,
                            f"🚨 <b>КРИТИЧЕСКАЯ ОШИБКА!</b>\n\n"
                            f"💀 Прокси отвалился и перестал отвечать:\n"
                            f"🌐 <code>{short_url}</code>\n\n"
                            f"🔧 <i>Он исключен из выдачи пользователям.</i>"
                        )

                await session.commit()
                await asyncio.sleep(0.5)  # Пауза между проверками разных прокси

        # Ждем 3 минуты до следующего круга
        await asyncio.sleep(180)