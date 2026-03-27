from aiogram import Router
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, KICKED, MEMBER
from aiogram.types import ChatMemberUpdated
from database.requests.update import update_user_status

router = Router()

# Пользователь заблокировал бота
@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED))
async def user_blocked_bot(event: ChatMemberUpdated):
    await update_user_status(event.from_user.id, False)

# Пользователь разблокировал бота
@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def user_unblocked_bot(event: ChatMemberUpdated):
    await update_user_status(event.from_user.id, True)