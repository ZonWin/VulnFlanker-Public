from fastapi import APIRouter

from app.api.routes import agent_downloads, agent_ingress, health

agent_router = APIRouter()
agent_router.include_router(health.router, prefix="/health", tags=["agent-health"])
agent_router.include_router(agent_ingress.router, tags=["agent-ingress"])
agent_router.include_router(agent_downloads.router, prefix="/downloads", tags=["agent-downloads"])
