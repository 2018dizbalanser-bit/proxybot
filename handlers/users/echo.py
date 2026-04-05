import re
from aiogram import Router, F, types
from data.config import ADMIN_IDS
from database.requests.get import get_ad_link_stats, create_ad_link

router = Router()


@router.message(F.text)
async def handle_unknown_text(message: types.Message):
    text = message.text.strip()

    # Регулярка для ссылок t.me/bot?start=xxx
    match = re.search(r't\.me/\w+\?start=([a-zA-Z0-9_-]+)', text)

    if match:
        ref_name = match.group(1)

        if ref_name.startswith('prx_'):
            await message.answer("❌ Префикс <code>prx_</code> зарезервирован для системных прокси.")
            return

        stats = await get_ad_link_stats(ref_name)

        if stats:
            interacted_blocked = stats['interacted_total'] - stats['interacted_active']

            stats_text = (
                f"📈 <b>Статистика:</b> <code>{stats['name']}</code>\n"
                f"🕒 Запущена {stats['created_at'].strftime('%d.%m.%Y')}\n\n"

                f"👥 <b>Привлеченная аудитория:</b>\n"
                f"• Пришло в бота: <b>{stats['total']}</b> (из {stats['clicks']} кликов)\n"
                f"• Премиум-юзеров: <b>{stats['premium_percent']}%</b> ⭐️\n\n"

                f"🎯 <b>Целевые действия:</b>\n"
                f"• Нажали старт: <b>{stats['total']}</b>\n"
                f"• Взяли минимум 1 прокси: <b>{stats['interacted_total']}</b>\n\n"

                f"📊 <b>Удержание (Retention):</b>\n"
                f"• Живых из тех, кто нажал старт: <b>{stats['active']}</b> из {stats['total']}\n"
                f"• Живых из тех, кто брал прокси: <b>{stats['interacted_active']}</b> из {stats['interacted_total']}\n\n"

                f"📅 <b>Прирост:</b> День: +{stats['today']} | Неделя: +{stats['week']} | Месяц: +{stats['month']}"
            )
            await message.answer(stats_text)
            return

        else:
            if message.from_user.id in ADMIN_IDS:
                # Если у тебя функция создания ссылки называется по-другому, подправь тут
                await create_ad_link(ref_name)
                await message.answer(
                    f"✅ <b>Рекламная ссылка создана!</b>\n\n"
                    f"Метка: <code>{ref_name}</code>\n\n"
                    f"Отправьте мне эту ссылку снова в любой момент, чтобы увидеть подробную статистику."
                )
                return
            else:
                await message.answer("❌ Такая ссылка не найдена в базе трекера.")
                return

    # Заглушка на непонятный текст
    await message.answer(
        "🤔 Я не понимаю эту команду или текст.\n\n"
        "Пожалуйста, отправьте /start или воспользуйтесь кнопками меню внизу экрана."
    )