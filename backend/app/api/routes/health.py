from fastapi import APIRouter, HTTPException

from app.schemas.health import HealthResponse
from app.services.health import probe_dependencies

router = APIRouter()


@router.get("/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok", checks={"application": "up"})


@router.get("/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    result = probe_dependencies()
    if result.status != "ok":
        raise HTTPException(status_code=503, detail=result.model_dump())
    return result

