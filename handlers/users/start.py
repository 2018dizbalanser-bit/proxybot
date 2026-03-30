from aiogram import Router, types
from aiogram.filters import CommandStart, CommandObject

from database.requests.add import add_user
from keyboards.reply import main_keyboard

# Импортируем функцию выдачи конкретного прокси (мы её напишем в Шаге 3)
from handlers.users.proxy import send_specific_proxy

router = Router()

@router.message(CommandStart())
async def start_command(message: types.Message, command: CommandObject, bot: Bot):
    # Добавляем пользователя в БД
    await add_user(
        tg_id=message.from_user.id,
        username=message.from_user.username
    )

    args = command.args

    if args and args.startswith("prx_"):
        try:
            proxy_id = int(args.split("_")[1])
            # Передаем bot сюда!
            await send_specific_proxy(message, proxy_id, bot)
            return
        except ValueError:
            pass


    # Если это обычный старт (без реферальной ссылки)
    text = (
        f"<b>Привет, {message.from_user.first_name}!</b> 👋\n\n"
        f"Я — умный каталог <b>MTProto-прокси</b>. Выдаю сервера, которые не тормозят!\n\n"
        f"⚡️ <b>Что я умею:</b>\n"
        f"• <b>Честный рейтинг:</b> топ формируют лайки (👍/👎) пользователей.\n"
        f"• <b>Никаких лагов:</b> регулярно проверяю пинг всех прокси в системе.\n"
        f"• <b>Продвижение:</b> добавь свой прокси в личном кабинете "
        f"и бесплатно получай подписчиков на свой спонсорский канал!\n\n"
        f"👇 <b>Нажимай кнопку в меню, чтобы начать:</b>"
    )

    await message.answer(
        text,
        reply_markup=main_keyboard()
    )