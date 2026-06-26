"""Health-check API routes for operational probes."""

from compliance.config import settings
from compliance.db.db_access import (
    verify_db_coherence_with_python_models,
    verify_db_is_reachable,
    verify_latest_migration_script,
)
from compliance.services.attachments import check_attachment_storage
from compliance.services.schemas import HealthCheckResult
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def liveness_check() -> dict[str, str]:
    """Return a minimal process liveness signal."""
    return {"status": "alive"}


@router.get("/ready")
def readiness_check() -> HealthCheckResult:
    """Return dependency readiness details or raise 503 when not ready."""
    is_reachable = verify_db_is_reachable()
    if not is_reachable:
        raise HTTPException(status_code=503, detail="Database unreachable.")

    if not verify_latest_migration_script(
        settings.app_env
    ) or not verify_db_coherence_with_python_models(settings.app_env):
        raise HTTPException(status_code=503, detail="Database not up to date.")

    if not check_attachment_storage():
        raise HTTPException(status_code=503, detail="Attachment storage unreachable.")

    return HealthCheckResult.model_validate(
        {
            "database_reachable": True,
            "migration_current": True,
            "model_drift_absent": True,
            "attachment_storage": True,
        }
    )
