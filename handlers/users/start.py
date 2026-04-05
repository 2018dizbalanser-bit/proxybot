from aiogram import Router, types, F, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from database.requests.add import add_user
from database.requests.get import get_proxy_by_id, increment_ad_click
from keyboards.reply import main_keyboard
from handlers.users.proxy import send_specific_proxy

router = Router()


# --- Вспомогательная функция для проверки подписки ---
async def check_user_subscription(bot: Bot, user_id: int, channel_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return True


@router.message(CommandStart())
async def start_command(message: types.Message, command: CommandObject, bot: Bot):
    args = command.args
    ref_name = None

    # Обработка аргументов (прокси или реклама)
    if args:
        if args.startswith("prx_"):
            loading_msg = await message.answer(
                "🔄 <i>Проверяю информацию о сервере...</i>",
                reply_markup=types.ReplyKeyboardRemove()
            )

            try:
                proxy_id = int(args.split("_")[1])
                proxy = await get_proxy_by_id(proxy_id)

                if not proxy or not proxy.is_active:
                    await loading_msg.delete()
                    await message.answer(
                        "😔 <b>Этот прокси больше недоступен или был удален владельцем.</b>\nВоспользуйтесь кнопкой ниже, чтобы найти другой рабочий сервер.",
                        reply_markup=main_keyboard()
                    )
                    return

                if proxy.sponsor_until and proxy.sponsor_until > datetime.utcnow() and proxy.sponsor_channel_id:
                    is_subscribed = await check_user_subscription(bot, message.from_user.id, proxy.sponsor_channel_id)

                    if not is_subscribed:
                        await loading_msg.delete()
                        builder = InlineKeyboardBuilder()
                        builder.row(types.InlineKeyboardButton(text="📢 Подписаться на Спонсора", url=proxy.sponsor_channel_url))
                        builder.row(types.InlineKeyboardButton(text="✅ Проверить подписку", callback_data=f"check_sponsor_{proxy_id}"))

                        await message.answer(
                            "🛑 <b>Обязательная подписка!</b>\n\n"
                            "Чтобы получить доступ к этому приватному прокси-серверу, вы должны быть подписаны на канал спонсора сервера.\n\n"
                            "<i>Подпишитесь и нажмите «Проверить подписку» 👇</i>",
                            reply_markup=builder.as_markup()
                        )
                        return

                await loading_msg.delete()
                await message.answer(f"Нажмите «Подключиться», чтобы добавить его в Telegram. 👇", reply_markup=main_keyboard())
                await send_specific_proxy(message, proxy_id, bot)
                return


            except Exception as e:

                # Теперь бот не будет падать из-за двойного удаления

                # и мы увидим настоящую ошибку в консоли, если она случится!

                print(f"Ошибка при выдаче прокси по ссылке: {e}")

                try:

                    await loading_msg.delete()

                except Exception:

                    pass
        else:
            # Это рекламная метка
            ref_name = args
            await increment_ad_click(ref_name)

    # Добавляем или обновляем пользователя в БД (с учетом ref_name и premium)
    await add_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        ref_name=ref_name,
        is_premium=message.from_user.is_premium or False  # <--- Передаем статус из Telegram
    )

    # Стандартное меню (если пришел без ссылки или по рекламной)
    if not args or not args.startswith("prx_"):
        text = (f"<b>Привет, {message.from_user.first_name}!</b> 👋\n\n"
                f"Я — умный каталог MTProto-прокси. Выдаю сервера, которые не тормозят!\n\n"
                f"⚡️ <b>Что я умею:</b>\n"
                f"• <b>Честный рейтинг:</b> топ формируют лайки (👍/👎) пользователей.\n"
                f"• <b>Никаких лагов:</b> регулярно проверяю пинг всех прокси в системе.\n"
                f"• <b>Продвижение:</b> добавь свой прокси в личном кабинете и бесплатно получай подписчиков на свой спонсорский канал!\n\n"
                f"👇 Нажимай кнопку в меню, чтобы начать:")

        await message.answer(text, reply_markup=main_keyboard())


# --- Хендлер кнопки "Проверить подписку" ---
@router.callback_query(F.data.startswith("check_sponsor_"))
async def check_sponsor_callback(callback: types.CallbackQuery, bot: Bot):
    proxy_id = int(callback.data.split("_")[2])
    proxy = await get_proxy_by_id(proxy_id)

    if not proxy or not proxy.sponsor_channel_id or proxy.sponsor_until < datetime.utcnow():
        await callback.answer("Спонсор больше не актуален, выдаю прокси!", show_alert=True)
        await callback.message.delete()
        await callback.message.answer("✅ <b>Доступ разрешен!</b>\n<i>Главное меню бота доступно внизу 👇</i>",
                                      reply_markup=main_keyboard())
        await send_specific_proxy(callback.message, proxy_id, bot)
        return

    is_subscribed = await check_user_subscription(bot, callback.from_user.id, proxy.sponsor_channel_id)

    if is_subscribed:
        await callback.answer("✅ Подписка подтверждена!", show_alert=True)
        await callback.message.delete()

        # Возвращаем главное меню после успешной подписки
        await callback.message.answer("✅ <b>Подписка подтверждена!</b>\n<i>Главное меню бота доступно внизу 👇</i>",
                                      reply_markup=main_keyboard())
        await send_specific_proxy(callback.message, proxy_id, bot)
    else:
        await callback.answer("❌ Вы не подписались на канал! Пожалуйста, перейдите по ссылке и попробуйте снова.",
                              show_alert=True)