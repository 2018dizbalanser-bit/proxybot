import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN")

# База данных
DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///database.db")

# Получаем ID админов и преобразуем в список int
def get_admin_ids() -> list[int]:
    admins = os.getenv("ADMIN_IDS", "")
    if not admins:
        return []
    return [int(admin_id.strip()) for admin_id in admins.split(",") if admin_id.strip().isdigit()]

ADMIN_IDS = get_admin_ids()


# --- Цены в Telegram Stars (XTR) ---
PRICE_SLOT = 10               # Цена за +1 слот навсегда
PRICE_SPONSOR_7_DAYS = 50     # ОП на 7 дней
PRICE_SPONSOR_30_DAYS = 150   # ОП на 30 дней (выгоднее!)
PRICE_BOOST = 50              # Буст в ТОП (задел на будущее)