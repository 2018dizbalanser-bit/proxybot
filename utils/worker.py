import asyncio
from datetime import datetime
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import types

from database.connect import async_session
from database.models import Proxy
from sqlalchemy import select
from utils.ping import ping_proxy, parse_proxy_url
from utils.i18n import t


async def _get_owner_lang(owner_id: int) -> str:
    """Получает язык владельца прокси из БД."""
    from database.requests.get import get_user
    user = await get_user(owner_id)
    return user.language if (user and user.language) else 'ru'


async def notify_owner(bot: Bot, owner_id: int | None, text_key: str,
                       btn_key: str = None, btn_callback: str = None, **kwargs):
    if not owner_id:
        return
    try:
        lang = await _get_owner_lang(owner_id)
        text = t(text_key, lang, **kwargs)
        markup = None
        if btn_key and btn_callback:
            markup = InlineKeyboardBuilder().row(
                types.InlineKeyboardButton(
                    text=t(btn_key, lang),
                    callback_data=btn_callback
                )
            ).as_markup()
        await bot.send_message(
            chat_id=owner_id,
            text=text,
            reply_markup=markup,
            disable_web_page_preview=True
        )
    except Exception:
        pass


async def _ping_task(proxy_id: int, host: str, port: int, semaphore: asyncio.Semaphore):
    async with semaphore:
        is_alive, resp_time = await ping_proxy(host, port)
        return proxy_id, is_alive, resp_time


async def background_proxy_checker(bot: Bot):
    proxy_strikes = {}
    semaphore = asyncio.Semaphore(50)

    while True:
        try:
            async with async_session() as session:
                result = await session.execute(select(Proxy))
                proxies = result.scalars().all()

                for proxy in proxies:

                    if proxy.sponsor_until and proxy.sponsor_until < datetime.utcnow():
                        proxy_id = proxy.id
                        owner_id = proxy.owner_id
                        proxy.sponsor_channel_id = None
                        proxy.sponsor_channel_url = None
                        proxy.sponsor_until = None

                        if owner_id:
                            asyncio.create_task(notify_owner(
                                bot, owner_id,
                                text_key='worker_sponsor_expired',
                                btn_key='btn_extend_op',
                                btn_callback=f"sponsor_menu_{proxy_id}",
                                proxy_id=proxy_id
                            ))

                    if proxy.boost_until and proxy.boost_until < datetime.utcnow():
                        proxy_id = proxy.id
                        owner_id = proxy.owner_id
                        proxy.boost_until = None

                        if owner_id:
                            asyncio.create_task(notify_owner(
                                bot, owner_id,
                                text_key='worker_boost_expired',
                                btn_key='btn_extend_boost',
                                btn_callback=f"buy_boost_{proxy_id}",
                                proxy_id=proxy_id
                            ))

                ping_tasks = []
                for proxy in proxies:
                    host, port = parse_proxy_url(proxy.url)
                    if host and port:
                        ping_tasks.append(_ping_task(proxy.id, host, port, semaphore))

                ping_results = await asyncio.gather(*ping_tasks)
                ping_dict = {res[0]: (res[1], res[2]) for res in ping_results}

                for proxy in proxies:
                    if proxy.id not in ping_dict:
                        continue

                    is_alive, resp_time = ping_dict[proxy.id]
                    was_active = proxy.is_active

                    if is_alive:
                        proxy_strikes[proxy.id] = 0
                        proxy.is_active = True
                        proxy.success_checks += 1
                        proxy.total_checks += 1
                        proxy.score = float(proxy.likes - proxy.dislikes - (resp_time / 100.0))
                    else:
                        current_strikes = proxy_strikes.get(proxy.id, 0) + 1
                        proxy_strikes[proxy.id] = current_strikes
                        proxy.total_checks += 1

                        if current_strikes >= 3:
                            proxy.is_active = False
                            proxy.score = 9999.0

                            if was_active:
                                short_url = proxy.url.split('@')[-1] if '@' in proxy.url else proxy.url
                                asyncio.create_task(notify_owner(
                                    bot, proxy.owner_id,
                                    text_key='worker_proxy_dead',
                                    short_url=short_url
                                ))

                await session.commit()

        except Exception as e:
            print(f"Ошибка в воркере: {e}")

        await asyncio.sleep(180)
