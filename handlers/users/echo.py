import re
from aiogram import Router, F, types
from data.config import ADMIN_IDS
from database.requests.get import get_ad_link_stats, create_ad_link
from utils.i18n import t

router = Router()


@router.message(F.text)
async def handle_unknown_text(message: types.Message, lang: str):
    text = message.text.strip()
    match = re.search(r't\.me/\w+\?start=([a-zA-Z0-9_-]+)', text)

    if match:
        ref_name = match.group(1)

        if ref_name.startswith('prx_'):
            await message.answer(t('echo_reserved_prefix', lang))
            return

        stats = await get_ad_link_stats(ref_name)

        if stats:
            # Статистика для админов — остаётся на русском
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
                await create_ad_link(ref_name)
                await message.answer(t('echo_link_created', lang, ref_name=ref_name))
                return
            else:
                await message.answer(t('echo_link_not_found', lang))
                return

    await message.answer(t('echo_unknown', lang))
