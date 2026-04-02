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
            # Выводим дизайн админки
            stats_text = (
                f"📊 <b>Статистика рекламной кампании</b>\n"
                f"🏷 Метка: <code>{stats['name']}</code>\n"
                f"📅 Создана: {stats['created_at'].strftime('%d.%m.%Y')}\n\n"
                f"🔗 Всего переходов (кликов): <b>{stats['clicks']}</b>\n\n"
                f"👥 <b>Конверсия пользователей:</b>\n"
                f"Всего зашло в бота: <b>{stats['total']}</b>\n"
                f"🟢 Живых (активных): <b>{stats['active']}</b>\n"
                f"🔴 Удалили бота: <b>{stats['blocked']}</b>\n\n"
                f"📈 <b>Динамика прихода:</b>\n"
                f"Сегодня: <b>+{stats['today']}</b>\n"
                f"Вчера: <b>+{stats['yesterday']}</b>\n"
                f"За неделю: <b>+{stats['week']}</b>\n"
                f"За месяц: <b>+{stats['month']}</b>"
            )
            await message.answer(stats_text)
            return

        else:
            if message.from_user.id in ADMIN_IDS:
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