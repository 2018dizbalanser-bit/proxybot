import asyncio
from datetime import datetime

from aiogram import Bot, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
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


async def notify_owner(bot: Bot, owner_id: int | None, text: str, reply_markup=None):
    """Отправляет уведомление владельцу прокси"""
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
        pass  # Владелец мог заблокировать бота


async def background_proxy_checker(bot: Bot):
    """Фоновая задача для проверки всех прокси каждые 3 минуты с алертами"""
    while True:
        async with async_session() as session:
            result = await session.scalars(select(Proxy))
            proxies = result.all()

            for proxy in proxies:
                # --- НОВЫЙ БЛОК: ПРОВЕРКА ИСТЕЧЕНИЯ СПОНСОРА ---
                if proxy.sponsor_until and proxy.sponsor_until < datetime.utcnow():
                    # Сохраняем ID перед очисткой
                    proxy_id = proxy.id
                    owner_id = proxy.owner_id

                    # 1. Очищаем спонсора в БД
                    proxy.sponsor_channel_id = None
                    proxy.sponsor_channel_url = None
                    proxy.sponsor_until = None

                    # 2. Отправляем уведомление с кнопкой
                    if owner_id:
                        markup = InlineKeyboardBuilder().row(
                            types.InlineKeyboardButton(
                                text="📢 Продлить спонсора (50 ⭐️)",
                                callback_data=f"buy_sponsor_{proxy_id}"
                            )
                        ).as_markup()

                        text = (
                            f"🔔 <b>Срок спонсорства истек!</b>\n\n"
                            f"Привязка канала к вашему прокси <b>#{proxy_id}</b> завершена. "
                            f"Люди, переходящие по вашей реферальной ссылке, больше не обязаны подписываться на ваш канал.\n\n"
                            f"👇 Нажмите кнопку ниже, чтобы возобновить конверсию трафика:"
                        )
                        await notify_owner(bot, owner_id, text, reply_markup=markup)


                # Запоминаем состояние ДО проверки
                was_active = proxy.is_active
                old_score = proxy.score

                # Пингуем
                tcp_ping, resp_time = await ping_proxy(proxy.url)

                proxy.total_checks += 1

                if tcp_ping is not None and resp_time is not None:
                    proxy.success_checks += 1
                    proxy.is_active = True

                    # 1. Считаем базовый сетевой скор
                    raw_score = (tcp_ping * 0.3) + (resp_time * 0.7)

                    # 2. Влияние Premium-голосования
                    rating_modifier = (proxy.premium_dislikes * 50.0) - (proxy.premium_likes * 20.0)
                    new_score = raw_score + rating_modifier

                    if new_score < 1.0:
                        new_score = 1.0

                    proxy.score = new_score

                    # АЛЕРТ 1: Сильная деградация
                    if old_score < 1500 and new_score >= 1500:
                        short_url = proxy.url.split('@')[-1] if '@' in proxy.url else proxy.url

                        alert_text = (
                            f"⚠️ <b>Внимание! Ваш прокси деградирует!</b>\n\n"
                            f"🌐 <code>{short_url}</code>\n\n"
                            f"📉 Рейтинг (скор) упал до <b>{round(new_score, 1)}</b>.\n"
                            f"<i>Сервер перегружен или получил много Premium-дизлайков.</i>"
                        )

                        # Если есть владелец — пишем ему. Если нет (системный прокси) — пишем админам.
                        if proxy.owner_id:
                            await notify_owner(bot, proxy.owner_id, alert_text)
                        else:
                            await notify_admins(bot,
                                                f"⚠️ [Админ] Деградация системного прокси:\n<code>{short_url}</code>")

                else:
                    proxy.is_active = False
                    proxy.score = 9999.0

                    # АЛЕРТ 2: Прокси отвалился (был активен, а теперь нет)
                    if was_active:
                        short_url = proxy.url.split('@')[-1] if '@' in proxy.url else proxy.url

                        alert_text = (
                            f"🚨 <b>Ваш прокси перестал работать!</b>\n\n"
                            f"💀 Он не отвечает на пинг и временно исключен из выдачи:\n"
                            f"🌐 <code>{short_url}</code>\n\n"
                            f"🔧 <i>Пожалуйста, проверьте работу сервера.</i>"
                        )

                        if proxy.owner_id:
                            await notify_owner(bot, proxy.owner_id, alert_text)
                        else:
                            await notify_admins(bot, f"🚨 [Админ] Системный прокси мертв:\n<code>{short_url}</code>")

                await session.commit()
                await asyncio.sleep(0.2)  # Пауза между проверками разных прокси

        # Ждем 3 минуты до следующего круга
        await asyncio.sleep(180)