from datetime import datetime, timedelta

from sqlalchemy import select, func, and_, case
from database.connect import async_session
from database.models import User, Channel, Proxy, AdLink, ProxyView, Vote


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


async def get_best_proxy(user_id: int, exclude_id: int = None, is_replace: bool = False):
    async with async_session() as session:
        now = datetime.utcnow()

        query = (
            select(Proxy)
            .outerjoin(ProxyView, and_(ProxyView.proxy_id == Proxy.id, ProxyView.user_id == user_id))
            .outerjoin(Vote, and_(Vote.proxy_id == Proxy.id, Vote.user_id == user_id))
            .where(Proxy.is_active == True, Proxy.is_public == True)
        )

        if exclude_id:
            query = query.where(Proxy.id != exclude_id)

        if not is_replace:
            # 🚀 ГЛАВНАЯ КНОПКА (Промо решают)
            query = query.order_by(
                case(
                    (Vote.is_upvote == False, 4),
                    (and_(Proxy.boost_until > now, ProxyView.id.is_(None)), 0),
                    (and_(Proxy.boost_until > now, ProxyView.id.is_not(None)), 1),
                    (ProxyView.id.is_(None), 2),
                    else_=3
                ),
                # МАГИЯ ТУТ: Сначала старые просмотры, потом рейтинг
                ProxyView.viewed_at.asc(),
                Proxy.score.desc()
            )
        else:
            # 🔄 КНОПКА ЗАМЕНЫ (Просто дай лучший сервер)
            query = query.order_by(
                case(
                    (Vote.is_upvote == False, 2),
                    (ProxyView.id.is_(None), 0),
                    else_=1
                ),
                # МАГИЯ ТУТ: Круговая карусель для просмотренных
                ProxyView.viewed_at.asc(),
                Proxy.score.desc()
            )

        query = query.limit(1)
        result = await session.execute(query)
        return result.scalar_one_or_none()


# Функция для фиксации просмотра
async def mark_proxy_viewed(user_id: int, proxy_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(ProxyView).where(ProxyView.user_id == user_id, ProxyView.proxy_id == proxy_id)
        )
        view = result.scalar_one_or_none()

        if not view:
            # Юзер видит сервер впервые
            new_view = ProxyView(user_id=user_id, proxy_id=proxy_id)
            session.add(new_view)
        else:
            # Юзер видит сервер повторно — обновляем время на "сейчас"!
            view.viewed_at = datetime.utcnow()

        await session.commit()


async def check_if_viewed(user_id: int, proxy_id: int) -> bool:
    """Проверяет, видел ли пользователь этот прокси ранее"""
    async with async_session() as session:
        result = await session.execute(
            select(ProxyView).where(
                ProxyView.user_id == user_id,
                ProxyView.proxy_id == proxy_id
            )
        )
        return result.scalar_one_or_none() is not None


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


async def get_proxy_by_id(proxy_id: int):
    async with async_session() as session:
        return await session.get(Proxy, proxy_id)



# Замени get_user_proxy на эту функцию
async def get_user_proxies(user_id: int):
    async with async_session() as session:
        # Убрали .limit(1), теперь получаем все прокси пользователя
        result = await session.execute(
            select(Proxy).where(Proxy.owner_id == user_id)
        )
        return result.scalars().all()



# Не забудь убедиться, что select импортирован (from sqlalchemy import select)
async def get_user(tg_id: int):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        return result.scalar_one_or_none()



async def get_ad_link(name: str):
    async with async_session() as session:
        result = await session.execute(select(AdLink).where(AdLink.name == name))
        return result.scalar_one_or_none()

async def create_ad_link(name: str):
    async with async_session() as session:
        new_link = AdLink(name=name)
        session.add(new_link)
        await session.commit()

async def increment_ad_click(name: str):
    """Увеличивает счетчик ВСЕХ кликов по ссылке"""
    async with async_session() as session:
        result = await session.execute(select(AdLink).where(AdLink.name == name))
        ad_link = result.scalar_one_or_none()
        if ad_link:
            ad_link.clicks += 1
            await session.commit()


async def get_ad_link_stats(ref_name: str) -> dict:
    """Собирает админскую статистику по конкретной реферальной ссылке"""
    async with async_session() as session:
        # Проверяем, существует ли ссылка
        link_res = await session.execute(select(AdLink).where(AdLink.name == ref_name))
        ad_link = link_res.scalar_one_or_none()

        if not ad_link:
            return None

        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_start = today_start - timedelta(days=7)
        month_start = today_start - timedelta(days=30)

        # Вытаскиваем всех юзеров по этой ссылке
        users_res = await session.execute(select(User).where(User.ref_name == ref_name))
        users = users_res.scalars().all()

        total = len(users)
        active = sum(1 for u in users if u.is_active)
        blocked = total - active

        today = sum(1 for u in users if u.created_at >= today_start)
        yesterday = sum(1 for u in users if yesterday_start <= u.created_at < today_start)
        week = sum(1 for u in users if u.created_at >= week_start)
        month = sum(1 for u in users if u.created_at >= month_start)

        return {
            "name": ad_link.name,
            "clicks": ad_link.clicks,
            "created_at": ad_link.created_at,
            "total": total,
            "active": active,
            "blocked": blocked,
            "today": today,
            "yesterday": yesterday,
            "week": week,
            "month": month
        }


async def get_user_liked_proxies(user_id: int):
    """Получает список живых прокси, которые лайкнул пользователь"""
    async with async_session() as session:
        # Джойним таблицы: берем прокси, если есть запись в Vote с лайком от этого юзера
        query = select(Proxy).join(Vote, Vote.proxy_id == Proxy.id).where(
            Vote.user_id == user_id,
            Vote.is_upvote == True,
            Proxy.is_active == True  # Показываем только живые!
        ).order_by(Proxy.score.desc()).limit(15)  # Ограничим до 15 лучших, чтобы не перегружать интерфейс

        result = await session.execute(query)
        return result.scalars().all()


from sqlalchemy import select, func
from database.models import ProxyView, Vote, Proxy

async def get_user_stats_for_cabinet(user_id: int) -> dict:
    """Собирает статистику активности пользователя для Личного кабинета"""
    async with async_session() as session:
        # Считаем просмотренные прокси
        viewed_res = await session.execute(
            select(func.count(ProxyView.id)).where(ProxyView.user_id == user_id)
        )
        viewed_count = viewed_res.scalar() or 0

        # Считаем лайкнутые (добавленные в избранное)
        liked_res = await session.execute(
            select(func.count(Vote.id)).where(Vote.user_id == user_id, Vote.is_upvote == True)
        )
        liked_count = liked_res.scalar() or 0

        # Считаем добавленные сервера (для партнеров)
        added_res = await session.execute(
            select(func.count(Proxy.id)).where(Proxy.owner_id == user_id)
        )
        added_count = added_res.scalar() or 0

        return {
            "viewed": viewed_count,
            "liked": liked_count,
            "added": added_count
        }