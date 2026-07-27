from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.api.agent_router import agent_router
from app.api.console_router import console_router
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    yield


def _create_app(*, title: str, description: str, router: APIRouter, prefix: str) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=title,
        version="0.1.0",
        description=description,
        lifespan=lifespan,
    )
    app.include_router(router, prefix=prefix)

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "environment": settings.app_env,
            "docs": "/docs",
        }

    return app


def create_legacy_app() -> FastAPI:
    settings = get_settings()
    return _create_app(
        title=settings.app_name,
        description="漏洞影响判定与受控验证平台骨架。",
        router=api_router,
        prefix=settings.api_prefix,
    )


def create_console_app() -> FastAPI:
    settings = get_settings()
    return _create_app(
        title=f"{settings.app_name} Console API",
        description="VulnFlanker 控制台 API。",
        router=console_router,
        prefix=settings.api_prefix,
    )


def create_agent_app() -> FastAPI:
    settings = get_settings()
    return _create_app(
        title=f"{settings.app_name} Agent Ingress",
        description="VulnFlanker Agent 数据上报入口。",
        router=agent_router,
        prefix=settings.agent_api_prefix,
    )
