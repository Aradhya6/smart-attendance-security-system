"""
API v1 Central Router
Aggregates all v1 endpoints under /api/v1.
"""
from fastapi import APIRouter

from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.health import router as health_router

api_v1_router = APIRouter(prefix="/api/v1")

# Mount sub-routers
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)

