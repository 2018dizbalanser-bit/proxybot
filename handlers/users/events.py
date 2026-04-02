from aiogram import Router
from aiogram.filters import ChatMemberUpdatedFilter, KICKED
from aiogram.types import ChatMemberUpdated
from database.connect import async_session
from database.models import User
from sqlalchemy import select

router = Router()

@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED))
async def user_blocked_bot(event: ChatMemberUpdated):
    """Срабатывает, когда пользователь останавливает (блокирует) бота"""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == event.from_user.id))
        user = result.scalar_one_or_none()
        if user:
            user.is_active = False
            await session.commit()