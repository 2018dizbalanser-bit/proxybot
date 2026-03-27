from aiogram import Router
from .admin import router as admin_router

def setup_admin_routers() -> Router:
    router = Router()
    router.include_router(admin_router)
    return router