from fastapi import FastAPI

from app.app_factory import create_legacy_app


def create_app() -> FastAPI:
    return create_legacy_app()


app = create_app()

