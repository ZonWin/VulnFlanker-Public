from fastapi import APIRouter
from fastapi import Depends

from app.api.deps import require_current_user
from app.api.routes import (
    ai,
    agents,
    assets,
    auth,
    audit,
    health,
    intel,
    matching,
    match_results,
    ownership,
    platform_settings,
    rule_config,
    task_center,
    verification_evidence,
    verification_tasks,
    vulnerabilities,
    vulnerability_reviews,
    vulnerability_ai_enrichments,
)

api_router = APIRouter()
console_auth = [Depends(require_current_user)]
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(
    platform_settings.router,
    prefix="/platform-settings",
    tags=["platform-settings"],
)
api_router.include_router(audit.router, prefix="/audit", tags=["audit"], dependencies=console_auth)
api_router.include_router(ai.router, prefix="/ai", tags=["ai"], dependencies=console_auth)
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"], dependencies=console_auth)
api_router.include_router(ownership.router, tags=["ownership"], dependencies=console_auth)
api_router.include_router(intel.router, prefix="/intel", tags=["intel"])
api_router.include_router(matching.router, prefix="/matching", tags=["matching"], dependencies=console_auth)
api_router.include_router(
    vulnerabilities.router,
    prefix="/vulnerabilities",
    tags=["vulnerabilities"],
    dependencies=console_auth,
)
api_router.include_router(
    vulnerability_reviews.router,
    prefix="/vulnerability-reviews",
    tags=["vulnerability-reviews"],
    dependencies=console_auth,
)
api_router.include_router(
    vulnerability_ai_enrichments.router,
    prefix="/vulnerability-ai-enrichments",
    tags=["vulnerability-ai-enrichments"],
    dependencies=console_auth,
)
api_router.include_router(
    match_results.router,
    prefix="/match-results",
    tags=["match-results"],
    dependencies=console_auth,
)
api_router.include_router(
    rule_config.router,
    prefix="/rule-config",
    tags=["rule-config"],
    dependencies=console_auth,
)
api_router.include_router(
    task_center.router,
    prefix="/task-center",
    tags=["task-center"],
    dependencies=console_auth,
)
api_router.include_router(
    verification_tasks.router,
    prefix="/verification-tasks",
    tags=["verification-tasks"],
    dependencies=console_auth,
)
api_router.include_router(
    verification_evidence.router,
    prefix="/verification-evidence",
    tags=["verification-evidence"],
    dependencies=console_auth,
)
