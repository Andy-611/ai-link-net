"""Versioned v1 API routers."""

from fastapi import APIRouter

from .children import router as children_router
from .entities import router as entities_router
from .friends import router as friends_router
from .fs import router as fs_router
from .mail import router as mail_router
from .messages import router as messages_router
from .parent import router as parent_router
from .providers import router as providers_router
from .sessions import router as sessions_router
from .trade import router as trade_router
from .ws_messages import router as ws_messages_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(parent_router)
v1_router.include_router(children_router)
v1_router.include_router(entities_router)
v1_router.include_router(friends_router)
v1_router.include_router(fs_router)
v1_router.include_router(mail_router)
v1_router.include_router(messages_router)
v1_router.include_router(sessions_router)
v1_router.include_router(trade_router)
v1_router.include_router(ws_messages_router)
v1_router.include_router(providers_router)

__all__ = ["v1_router"]
