from aiogram import Router
from .start import router as start_router
from .proxy import router as proxy_router
from .status import router as status_router
from .cabinet import router as cabinet_router
from .payments import router as payments_router

def setup_users_routers() -> Router:
    router = Router()
    router.include_router(start_router)
    router.include_router(proxy_router)
    router.include_router(status_router)
    router.include_router(cabinet_router)
    router.include_router(payments_router)
    return router