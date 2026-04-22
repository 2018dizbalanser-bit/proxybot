from datetime import datetime

from database.models import Proxy
from utils.ping import parse_proxy_url
from utils.i18n import t


def get_proxy_card_text(proxy: Proxy, bot_username: str, is_direct_link: bool = False,
                        is_viewed: bool = False, lang: str = 'ru') -> str:
    uptime = 100
    if proxy.total_checks > 0:
        uptime = round((proxy.success_checks / proxy.total_checks) * 100, 1)

    host, port = parse_proxy_url(proxy.url)
    display_host = host if host else t('proxy_card_hidden_host', lang)

    is_boosted = proxy.boost_until and proxy.boost_until > datetime.utcnow()

    badges = []
    if is_boosted:
        badges.append(t('proxy_card_badge_promo', lang))
    elif is_viewed:
        badges.append(t('proxy_card_badge_viewed', lang))
    else:
        badges.append(t('proxy_card_badge_new', lang))

    badge_str = f" | {' | '.join(badges)}" if not is_direct_link else ""

    text = t('proxy_card_main', lang,
             proxy_id=proxy.id,
             badge_str=badge_str,
             host=display_host,
             uptime=uptime)

    return text
