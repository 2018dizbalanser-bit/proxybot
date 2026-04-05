from datetime import datetime, timedelta

from sqlalchemy import select, func, and_, case, update
from database.connect import async_session
from database.models import User, Channel, Proxy, AdLink, ProxyView, Vote, Transaction, BotSettings


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
            # 🚀 ГЛАВНАЯ КНОПКА (Витрина и Реклама)
            query = query.order_by(
                # 1. Сначала отделяем мусор, промо и обычные
                case(
                    (Vote.is_upvote == False, 2), # Дизлайки всегда на дне
                    (Proxy.boost_until > now, 0), # ПРОМО на самом верху
                    else_=1                       # Обычные сервера посередине
                ),
                # 2. МАГИЯ ДЛЯ РЕКЛАМОДАТЕЛЕЙ: Рандомная ротация ПРОМО-серверов
                # func.random() перемешивает только 0-й уровень (Промо), давая всем равные показы
                case(
                    (Proxy.boost_until > now, func.random()),
                    else_=0
                ),
                # 3. МАГИЯ ДЛЯ ЮЗЕРОВ: Если Промо нет, выдаем АБСОЛЮТНЫЙ ТОП-1 по качеству
                Proxy.score.desc()
            )
        else:
            # 🔄 КНОПКА ЗАМЕНЫ (Поиск лучшего коннекта)
            query = query.order_by(
                # 1. Здесь нам плевать на Промо. Ищем новые для юзера сервера.
                case(
                    (Vote.is_upvote == False, 2),
                    (ProxyView.id.is_(None), 0),  # Сначала те, что еще НЕ видел
                    else_=1                       # Если новых нет, берем старые
                ),
                # 2. Карусель для просмотренных (чтобы не было эффекта пинг-понга между двумя)
                ProxyView.viewed_at.asc(),
                # 3. Внутри новых серверов всегда отдаем самый лучший по рейтингу
                Proxy.score.desc()
            )

        query = query.limit(1)
        result = await session.execute(query)
        return result.scalar_one_or_none()


async def mark_user_inactive(tg_id: int):
    """Помечает пользователя как неактивного (заблокировал бота)"""
    async with async_session() as session:
        await session.execute(update(User).where(User.tg_id == tg_id).values(is_active=False))
        await session.commit()


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


# --- Настройки бота (Цены) ---
async def get_bot_settings():
    """Получает настройки. Если их нет - создает стандартные."""
    async with async_session() as session:
        result = await session.execute(select(BotSettings).where(BotSettings.id == 1))
        settings = result.scalar_one_or_none()
        if not settings:
            settings = BotSettings()  # Стандартные цены из модели
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings


async def update_bot_price(field_name: str, new_price: int):
    """Обновляет конкретную цену в БД"""
    async with async_session() as session:
        settings = await get_bot_settings()
        # Прикрепляем объект к текущей сессии для изменения
        settings = await session.merge(settings)
        setattr(settings, field_name, new_price)
        await session.commit()


# --- Транзакции и Аналитика ---
async def add_transaction(user_id: int, amount: int, action: str):
    """Записывает успешную оплату"""
    async with async_session() as session:
        tx = Transaction(user_id=user_id, amount=amount, action=action)
        session.add(tx)
        await session.commit()


async def get_admin_analytics():
    """Собирает статистику для админ-панели"""
    async with async_session() as session:
        # 1. Считаем сервера
        total_proxies = await session.scalar(select(func.count(Proxy.id)))
        active_proxies = await session.scalar(select(func.count(Proxy.id)).where(Proxy.is_active == True))

        # 2. Считаем пользователей
        total_users = await session.scalar(select(func.count(User.id)))

        # 3. Финансы (группируем по типу услуги)
        tx_result = await session.execute(
            select(Transaction.action, func.sum(Transaction.amount))
            .group_by(Transaction.action)
        )
        finances = {row[0]: row[1] for row in tx_result.all()}

        return total_proxies, active_proxies, total_users, finances


# --- Рефералки (Рекламные ссылки) ---
async def get_referral_stats():
    """Собирает список рекламных меток и количество пришедших по ним юзеров"""
    async with async_session() as session:
        # Группируем юзеров по ref_name, исключая тех, кто пришел без ссылки
        result = await session.execute(
            select(User.ref_name, func.count(User.id))
            .where(User.ref_name.is_not(None))
            .group_by(User.ref_name)
            .order_by(func.count(User.id).desc())
        )
        return [{"name": row[0], "users": row[1]} for row in result.all()]


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
    """Собирает продвинутую статистику по рекламной ссылке (с воронкой)"""
    async with async_session() as session:
        link_res = await session.execute(select(AdLink).where(AdLink.name == ref_name))
        ad_link = link_res.scalar_one_or_none()

        if not ad_link:
            return None

        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_start = today_start - timedelta(days=7)
        month_start = today_start - timedelta(days=30)

        # 1. Вытаскиваем всех юзеров по этой ссылке
        users_res = await session.execute(select(User).where(User.ref_name == ref_name))
        users = users_res.scalars().all()

        total = len(users)
        active = sum(1 for u in users if u.is_active)
        blocked = total - active

        # Считаем Премиум юзеров
        premium_count = sum(1 for u in users if u.is_premium)
        premium_percent = round((premium_count / total * 100), 1) if total > 0 else 0

        # Динамика
        today = sum(1 for u in users if u.created_at >= today_start)
        yesterday = sum(1 for u in users if yesterday_start <= u.created_at < today_start)
        week = sum(1 for u in users if u.created_at >= week_start)
        month = sum(1 for u in users if u.created_at >= month_start)

        # 2. Воронка: Считаем тех, кто реально пользовался ботом (есть в ProxyView)
        interacted_res = await session.execute(
            select(User.tg_id, User.is_active)
            .join(ProxyView, ProxyView.user_id == User.tg_id)
            .where(User.ref_name == ref_name)
            .distinct()
        )
        interacted_users = interacted_res.all()  # список кортежей (tg_id, is_active)

        interacted_total = len(interacted_users)
        interacted_active = sum(1 for u in interacted_users if u.is_active)

        return {
            "name": ad_link.name,
            "clicks": ad_link.clicks,
            "created_at": ad_link.created_at,
            "total": total,
            "active": active,
            "blocked": blocked,
            "premium_percent": premium_percent,
            "interacted_total": interacted_total,
            "interacted_active": interacted_active,
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