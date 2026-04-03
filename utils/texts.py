from datetime import datetime

from database.models import Proxy
from utils.ping import parse_proxy_url


def get_public_proxy_text(proxy: Proxy, bot_username: str) -> str:
    """Генерирует единый красивый текст карточки прокси для общей выдачи"""

    uptime = 100
    if proxy.total_checks > 0:
        uptime = round((proxy.success_checks / proxy.total_checks) * 100, 1)

    # Вытаскиваем IP или домен
    host, port = parse_proxy_url(proxy.url)
    display_host = host if host else "Скрытый адрес"

    # Ссылка для шеринга
    share_link = f"https://t.me/{bot_username}?start=prx_{proxy.id}"

    return (
        f"⚡️ <b>Прокси #{proxy.id}</b> | <code>{display_host}</code>\n\n"
        f"🟢 Стабильность: <b>{uptime}%</b>\n"
        f"📊 Рейтинг пользователей: 👍 {proxy.likes} / 👎 {proxy.dislikes}\n\n"
        f"🔗 <b>Поделись этим прокси с друзьями:</b>\n"
        f"<code>{share_link}</code>\n\n"
        f"⚠️ <b>Частые причины проблем с подключением:</b>\n"
        f"• Включен VPN (они конфликтуют с прокси).\n"
        f"• Зависла сеть (помогает вкл/выкл режима полета на 5 сек).\n\n"
        f"<i>Оцени сервер! Если он начнет тормозить, жми «Другой прокси» 👇</i>"
    )


def get_proxy_card_text(proxy: Proxy, bot_username: str, is_direct_link: bool = False, is_viewed: bool = False) -> str:
    uptime = 100
    if proxy.total_checks > 0:
        uptime = round((proxy.success_checks / proxy.total_checks) * 100, 1)

    host, port = parse_proxy_url(proxy.url)
    display_host = host if host else "Скрытый адрес"
    share_link = f"https://t.me/{bot_username}?start=prx_{proxy.id}"

    status_badge = "👀 Просмотрено" if is_viewed else "✨ Новый для вас"
    if is_direct_link: status_badge = ""  # Для реф-ссылок не пишем

    # Проверяем активен ли буст сейчас
    is_boosted = proxy.boost_until and proxy.boost_until > datetime.utcnow()

    # Собираем плашки
    badges = []
    if is_boosted:
        badges.append("🔥 Промо")
    elif is_viewed:
        badges.append("👀 Просмотрено")
    else:
        badges.append("✨ Новый")

    badge_str = f" | {' | '.join(badges)}" if not is_direct_link else ""

    # Максимально чистый и минималистичный текст
    text = (
        f"⚡️ <b>Прокси #{proxy.id}</b>{badge_str}\n"
        f"<code>{display_host}</code>\n\n"
        f"🟢 Стабильность: <b>{uptime}%</b>\n"
        f"📊 Рейтинг: 👍 {proxy.likes} / 👎 {proxy.dislikes}\n\n"
    )

    # Добавляем советы и призыв к действию в правильном порядке
    if not is_direct_link:
        text += (
            f"⚠️ <b>Частые причины проблем с подключением:</b>\n"
            f"• Включен VPN (они конфликтуют с прокси).\n"
            f"• Зависла сеть (помогает вкл/выкл режима полета на 5 сек).\n\n"
            f"<i>Оцени сервер! Если он начнет тормозить, жми «Другой прокси» 👇</i>"
        )

    return text