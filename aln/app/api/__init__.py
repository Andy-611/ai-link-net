"""API package for FP backend servers."""

from fastapi import APIRouter

from .health import router as health_router
from .v1 import v1_router
from .well_known import router as well_known_router
from .ws import router as ws_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(well_known_router)
api_router.include_router(v1_router)
api_router.include_router(ws_router)

__all__ = ["api_router"]
