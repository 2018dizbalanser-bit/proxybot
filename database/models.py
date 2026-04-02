from datetime import datetime
from sqlalchemy import BigInteger, String, Boolean, DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs

class Base(AsyncAttrs, DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    proxy_limit: Mapped[int] = mapped_column(default=3, server_default='3')
    ref_name: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Channel(Base):
    __tablename__ = 'channels'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True) # ID канала (начинается с -100)
    title: Mapped[str] = mapped_column(String(100)) # Название канала для админки
    url: Mapped[str] = mapped_column(String(100)) # Ссылка для кнопки


class Proxy(Base):
    __tablename__ = 'proxies'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, server_default='1')

    # 1. Привязка к владельцу (кто добавил прокси)
    owner_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('users.tg_id', ondelete='SET NULL'),
                                                 nullable=True)

    # 2. Обычные голоса (для отображения на кнопках)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    dislikes: Mapped[int] = mapped_column(Integer, default=0)

    # 3. Premium голоса (для реального влияния на рейтинг)
    premium_likes: Mapped[int] = mapped_column(Integer, default=0)
    premium_dislikes: Mapped[int] = mapped_column(Integer, default=0)

    # Твои метрики (оставляем как есть)
    score: Mapped[float] = mapped_column(Float, default=9999.0)
    success_checks: Mapped[int] = mapped_column(Integer, default=0)
    total_checks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # НОВЫЕ ПОЛЯ ДЛЯ СПОНСОРА
    sponsor_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sponsor_channel_url: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sponsor_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Срок действия БУСТА
    boost_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)



# 4. Новая таблица для хранения голосов пользователей
class Vote(Base):
    __tablename__ = 'votes'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.tg_id', ondelete='CASCADE'))
    proxy_id: Mapped[int] = mapped_column(Integer, ForeignKey('proxies.id', ondelete='CASCADE'))

    # Каким был голос? True = лайк, False = дизлайк
    is_upvote: Mapped[bool] = mapped_column(Boolean)

    # Был ли у юзера Премиум в момент голосования?
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AdLink(Base):
    __tablename__ = 'ad_links'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    clicks: Mapped[int] = mapped_column(default=0)      # Всего переходов (кто нажал /start)
    new_users: Mapped[int] = mapped_column(default=0)   # Новых регистраций по ссылке
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)



class ProxyView(Base):
    __tablename__ = 'proxy_views'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    proxy_id: Mapped[int] = mapped_column(Integer, index=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)