from sqlalchemy import select
from database.connect import async_session
from database.models import User

async def update_user_status(tg_id: int, is_active: bool):
    """Обновляет статус активности пользователя"""
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        if user and user.is_active != is_active:
            user.is_active = is_active
            await session.commit()