from fastapi import APIRouter

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    FindingOut,
)
from compliance.services.query_db import (
    get_findings,
)

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("")
def get_findings_route(
    session: SessionDep,
    site_id: int | None = None,
    rule_id: int | None = None,
    open_only: bool = False,
) -> list[FindingOut]:
    """Return findings with optional filters.

    Args:
        session: Database session provided by FastAPI dependency injection.
        site_id: Optional site identifier used to limit findings to one site.
        rule_id: Optional rule identifier used to limit findings to one rule.
        open_only: When true, only return findings whose certification has no
            resolution date.

    Returns:
        Finding records serialized with certification, regulation, and rule
        context.
    """
    return get_findings(session, site_id, rule_id, open_only)
