from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import engine
from app.schemas.health import HealthResponse


def probe_dependencies() -> HealthResponse:
    settings = get_settings()
    checks = {"application": "up", "redis_configured": "yes" if settings.redis_url else "no"}

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = "up"
    except SQLAlchemyError:
        checks["database"] = "down"
        return HealthResponse(status="degraded", checks=checks)

    return HealthResponse(status="ok", checks=checks)

