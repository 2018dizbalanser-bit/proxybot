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
        f"<i>Оцени сервер! Если он начнет тормозить, жми «Другой прокси».</i>"
    )