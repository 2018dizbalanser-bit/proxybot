from sqlalchemy import select
from database.connect import async_session
from database.models import User, Channel, Proxy, Vote, AdLink


async def add_user(tg_id: int, username: str | None = None, ref_name: str | None = None):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()

        if not user:
            new_user = User(tg_id=tg_id, username=username, is_active=True, ref_name=ref_name)
            session.add(new_user)
        else:
            user.is_active = True
            if user.username != username:
                user.username = username
            # Если юзер уже был, но перешел по новой рефке, мы не перезаписываем его первый источник
        await session.commit()


async def add_channel(channel_id: int, title: str, url: str):
    async with async_session() as session:
        session.add(Channel(channel_id=channel_id, title=title, url=url))
        await session.commit()

async def add_proxy(url: str):
    async with async_session() as session:
        session.add(Proxy(url=url))
        await session.commit()


# Добавь Vote в импорты наверху, если его там нет:
# from database.models import User, Channel, Proxy, Vote

async def add_or_update_vote(user_id: int, proxy_id: int, is_upvote: bool, is_premium: bool) -> tuple[bool, str]:
    """
    Возвращает (успех: bool, сообщение: str)
    """
    async with async_session() as session:
        proxy = await session.get(Proxy, proxy_id)
        if not proxy:
            return False, "❌ Прокси не найден."

        # Ищем, голосовал ли уже этот юзер за этот прокси
        result = await session.execute(
            select(Vote).where(Vote.user_id == user_id, Vote.proxy_id == proxy_id)
        )
        vote = result.scalar_one_or_none()

        if vote:
            if vote.is_upvote == is_upvote:
                return False, "⚠️ Вы уже проголосовали так же!"

            # Юзер решил изменить голос (например, с лайка на дизлайк)
            # Отменяем старые счетчики
            if vote.is_upvote:
                proxy.likes -= 1
                if vote.is_premium: proxy.premium_likes -= 1
            else:
                proxy.dislikes -= 1
                if vote.is_premium: proxy.premium_dislikes -= 1

            # Применяем новые счетчики
            vote.is_upvote = is_upvote
            vote.is_premium = is_premium  # Обновляем статус премиума (вдруг он его купил)
            if is_upvote:
                proxy.likes += 1
                if is_premium: proxy.premium_likes += 1
            else:
                proxy.dislikes += 1
                if is_premium: proxy.premium_dislikes += 1

            msg = "✅ Ваш голос изменен!"
        else:
            # Юзер голосует впервые
            new_vote = Vote(user_id=user_id, proxy_id=proxy_id, is_upvote=is_upvote, is_premium=is_premium)
            session.add(new_vote)

            if is_upvote:
                proxy.likes += 1
                if is_premium: proxy.premium_likes += 1
            else:
                proxy.dislikes += 1
                if is_premium: proxy.premium_dislikes += 1

            msg = "✅ Ваш голос учтен!"

        await session.commit()
        return True, msg