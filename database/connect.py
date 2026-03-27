from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from database.models import Base
from data.config import DB_URL

# Создаем асинхронный движок
engine = create_async_engine(DB_URL, echo=False)

# Создаем фабрику сессий
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def create_tables():
    """Создает все таблицы, описанные в Base (User, Channel, Proxy)"""
    async with engine.begin() as conn:
        # В продакшене лучше использовать Alembic для миграций,
        # но для старта и автосоздания таблиц это идеальный вариант
        await conn.run_sync(Base.metadata.create_all)