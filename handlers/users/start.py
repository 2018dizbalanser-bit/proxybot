from aiogram import Router, types, F, Bot
from aiogram.filters import CommandStart, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

from database.requests.add import add_user
from database.requests.get import get_proxy_by_id, increment_ad_click
from keyboards.reply import main_keyboard
from handlers.users.proxy import send_specific_proxy
from utils.i18n import t, detect_lang

router = Router()


async def check_user_subscription(bot: Bot, user_id: int, channel_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return True


@router.message(CommandStart())
async def start_command(message: types.Message, command: CommandObject, bot: Bot, lang: str):
    args = command.args
    ref_name = None

    if args:
        if args.startswith("prx_"):
            loading_msg = await message.answer(
                t('start_checking_server', lang),
                reply_markup=types.ReplyKeyboardRemove()
            )

            try:
                proxy_id = int(args.split("_")[1])
                proxy = await get_proxy_by_id(proxy_id)

                if not proxy or not proxy.is_active:
                    await loading_msg.delete()
                    await message.answer(
                        t('start_proxy_unavailable', lang),
                        reply_markup=main_keyboard(lang)
                    )
                    return

                if proxy.sponsor_until and proxy.sponsor_until > datetime.utcnow() and proxy.sponsor_channel_id:
                    is_subscribed = await check_user_subscription(bot, message.from_user.id, proxy.sponsor_channel_id)

                    if not is_subscribed:
                        await loading_msg.delete()
                        builder = InlineKeyboardBuilder()
                        builder.row(types.InlineKeyboardButton(
                            text=t('btn_subscribe_sponsor', lang),
                            url=proxy.sponsor_channel_url
                        ))
                        builder.row(types.InlineKeyboardButton(
                            text=t('btn_check_subscription', lang),
                            callback_data=f"check_sponsor_{proxy_id}"
                        ))
                        await message.answer(
                            t('start_sponsor_required', lang),
                            reply_markup=builder.as_markup()
                        )
                        return

                await loading_msg.delete()
                await message.answer(t('start_click_to_connect', lang), reply_markup=main_keyboard(lang))
                await send_specific_proxy(message, proxy_id, bot)
                return

            except Exception as e:
                print(f"Ошибка при выдаче прокси по ссылке: {e}")
                try:
                    await loading_msg.delete()
                except Exception:
                    pass
        else:
            ref_name = args
            await increment_ad_click(ref_name)

    # Для новых пользователей используем язык из Telegram,
    # для вернувшихся — middleware уже поставил правильный lang из БД
    detected_lang = detect_lang(message.from_user.language_code)
    effective_lang = lang if lang != 'ru' else detected_lang

    await add_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        ref_name=ref_name,
        is_premium=message.from_user.is_premium or False,
        language=detected_lang
    )

    if not args or not args.startswith("prx_"):
        await message.answer(
            t('start_greeting', effective_lang, name=message.from_user.first_name),
            reply_markup=main_keyboard(effective_lang)
        )


@router.callback_query(F.data.startswith("check_sponsor_"))
async def check_sponsor_callback(callback: types.CallbackQuery, bot: Bot, lang: str):
    proxy_id = int(callback.data.split("_")[2])
    proxy = await get_proxy_by_id(proxy_id)

    if not proxy or not proxy.sponsor_channel_id or proxy.sponsor_until < datetime.utcnow():
        await callback.answer(t('proxy_sponsor_expired', lang), show_alert=True)
        await callback.message.delete()
        await callback.message.answer(t('proxy_access_granted', lang), reply_markup=main_keyboard(lang))
        await send_specific_proxy(callback.message, proxy_id, bot)
        return

    is_subscribed = await check_user_subscription(bot, callback.from_user.id, proxy.sponsor_channel_id)

    if is_subscribed:
        await callback.answer(t('proxy_sub_confirmed', lang), show_alert=True)
        await callback.message.delete()
        await callback.message.answer(t('proxy_sub_confirmed_full', lang), reply_markup=main_keyboard(lang))
        await send_specific_proxy(callback.message, proxy_id, bot)
    else:
        await callback.answer(t('proxy_not_subscribed', lang), show_alert=True)
