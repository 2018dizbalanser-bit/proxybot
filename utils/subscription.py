from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest


async def get_unsubscribed_channels(bot: Bot, user_id: int, channels: list) -> list:
    """
    Проверяет подписку и возвращает список каналов, на которые юзер ЕЩЕ НЕ подписан.
    Если список пуст — значит, подписан на все обязательные каналы.
    """
    unsubscribed = []

    if not channels:
        return unsubscribed

    for channel in channels:
        try:
            chat_member = await bot.get_chat_member(chat_id=channel.channel_id, user_id=user_id)

            # Если юзер покинул канал или забанен
            if chat_member.status not in ['member', 'administrator', 'creator']:
                unsubscribed.append(channel)

        except TelegramBadRequest:
            # Бот не админ в канале или неверный ID
            print(f"⚠️ Ошибка доступа к каналу {channel.title} ({channel.channel_id}). Бот там админ?")
            unsubscribed.append(channel)
        except Exception as e:
            print(f"⚠️ Ошибка при проверке подписки: {e}")
            unsubscribed.append(channel)

    return unsubscribed