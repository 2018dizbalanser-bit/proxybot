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


async def ping_proxy(proxy_url: str, timeout_seconds: int = 4) -> tuple[float | None, float | None]:
    host, port = parse_proxy_url(proxy_url)
    if not host or not port:
        return None, None

    start_tcp = time.time()
    try:
        # Замеряем чисто сетевой пинг (TCP)
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout_seconds
        )
        tcp_ping_ms = round((time.time() - start_tcp) * 1000, 2)

        # Замеряем время отклика (Нагрузка на сервер)
        start_response = time.time()
        writer.write(b"\x00\x01\x02")
        await writer.drain()

        try:
            await asyncio.wait_for(reader.read(1), timeout=2.0)
        except Exception:
            pass  # Если не ответил, но соединение держит - это тоже норм для некоторых прокси

        response_time_ms = round((time.time() - start_response) * 1000, 2)

        writer.close()
        await writer.wait_closed()

        return tcp_ping_ms, response_time_ms
    except Exception:
        return None, None