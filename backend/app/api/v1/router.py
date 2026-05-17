from fastapi import APIRouter

from app.api.v1.routes import auth, demo, health, tasks, workspaces

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(demo.router, prefix="/demo", tags=["demo"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(tasks.router, tags=["tasks"])
