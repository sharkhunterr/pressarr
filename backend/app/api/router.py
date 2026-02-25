"""API v1 root router."""

from fastapi import APIRouter

from app.api.system import router as system_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(system_router, prefix="/system", tags=["system"])
