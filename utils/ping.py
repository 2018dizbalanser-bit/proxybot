import time
import asyncio
from urllib.parse import urlparse, parse_qs


def parse_proxy_url(proxy_url: str):
    """Извлекает IP/домен и порт из любой ссылки на прокси"""
    host, port = None, None
    try:
        # Если это ссылка Telegram (proxy или socks)
        if "t.me/" in proxy_url or proxy_url.startswith("tg://"):
            parsed_url = urlparse(proxy_url)
            qs = parse_qs(parsed_url.query)
            if 'server' in qs and 'port' in qs:
                host = qs['server'][0]
                port = int(qs['port'][0])
        else:
            # Обычный http/socks прокси
            if "://" not in proxy_url:
                proxy_url = "http://" + proxy_url
            parsed_url = urlparse(proxy_url)
            host = parsed_url.hostname
            port = parsed_url.port
    except Exception:
        pass

    return host, port


async def ping_proxy(host: str, port: int, timeout: int = 2) -> tuple[bool, float]:
    """
    Проверяет доступность прокси с помощью чистого TCP Handshake.
    Возвращает (is_alive, response_time_ms)
    """
    start_time = time.time()
    try:
        # Пытаемся установить TCP-соединение с жестким таймаутом
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout
        )

        # Если код дошел сюда — соединение успешно установлено!
        connect_time_ms = (time.time() - start_time) * 1000

        # Вежливо закрываем соединение, чтобы не спамить сервер
        writer.close()
        await writer.wait_closed()

        return True, connect_time_ms

    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        # Сервер не ответил или отказал в подключении
        return False, 0.0