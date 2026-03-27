from datetime import datetime, timedelta

from sqlalchemy import select, func
from database.connect import async_session
from database.models import User, Channel, Proxy

async def get_all_users():
    async with async_session() as session:
        result = await session.scalars(select(User))
        return result.all()

async def get_all_channels():
    async with async_session() as session:
        result = await session.scalars(select(Channel))
        return result.all()

async def get_all_proxies():
    async with async_session() as session:
        result = await session.scalars(select(Proxy))
        return result.all()


async def get_best_proxy(exclude_id: int = None):
    async with async_session() as session:
        query = select(Proxy).where(Proxy.is_active == True)

        # Если юзер просит замену, исключаем его текущий прокси из поиска
        if exclude_id is not None:
            query = query.where(Proxy.id != exclude_id)

        result = await session.scalars(query)
        proxies = list(result.all())

        if not proxies:
            return None

        stable_proxies = []
        for p in proxies:
            uptime = (p.success_checks / p.total_checks * 100) if p.total_checks > 0 else 100
            if uptime >= 80 or p.total_checks < 5:
                stable_proxies.append(p)

        if not stable_proxies:
            stable_proxies = proxies

        stable_proxies.sort(key=lambda x: x.score)

        return stable_proxies[0]


async def get_users_stats() -> tuple[int, int]:
    """Возвращает (всего_пользователей, активных_пользователей)"""
    async with async_session() as session:
        # Используем func.count для быстрого подсчета на стороне СУБД
        total_users = await session.scalar(select(func.count(User.id)))
        active_users = await session.scalar(
            select(func.count(User.id)).where(User.is_active == True)
        )
        return total_users or 0, active_users or 0


async def get_detailed_stats():
    """Возвращает словарь с развернутой статистикой пользователей"""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    async with async_session() as session:
        # Общее кол-во и активные
        total = await session.scalar(select(func.count(User.id)))
        active = await session.scalar(select(func.count(User.id)).where(User.is_active == True))

        # Новые пользователи за периоды
        new_today = await session.scalar(
            select(func.count(User.id)).where(User.created_at >= today_start)
        )
        new_yesterday = await session.scalar(
            select(func.count(User.id)).where(
                User.created_at >= yesterday_start,
                User.created_at < today_start
            )
        )
        new_week = await session.scalar(
            select(func.count(User.id)).where(User.created_at >= week_start)
        )
        new_month = await session.scalar(
            select(func.count(User.id)).where(User.created_at >= month_start)
        )

        return {
            "total": total or 0,
            "active": active or 0,
            "today": new_today or 0,
            "yesterday": new_yesterday or 0,
            "week": new_week or 0,
            "month": new_month or 0
        }