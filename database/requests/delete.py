from database.connect import async_session
from database.models import Channel, Proxy

async def delete_channel_db(db_id: int):
    async with async_session() as session:
        channel = await session.get(Channel, db_id)
        if channel:
            await session.delete(channel)
            await session.commit()

async def delete_proxy_db(db_id: int):
    async with async_session() as session:
        proxy = await session.get(Proxy, db_id)
        if proxy:
            await session.delete(proxy)
            await session.commit()