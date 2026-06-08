from typing import Annotated

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    ArchiveRequest,
    RuleCreate,
    RuleOut,
)
from compliance.services.rules import (
    RuleConflictError,
    RuleIndexConflictError,
    RuleRegulationNotFoundError,
    get_rules,
    post_new_rule,
    post_rule_archived_by_id,
    post_rule_restored_by_id,
)
from fastapi import APIRouter, HTTPException, Path, Query

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("")
def get_rules_route(
    session: SessionDep,
    regulation_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_archived: Annotated[bool, Query()] = False,
) -> list[RuleOut]:
    """Return rules with optional filters and pagination.

    Args:
        session: Database session provided by FastAPI dependency injection.
        regulation_id: Optional regulation ID used to return rules for one
            regulation.
        limit: Maximum number of rules to return.
        offset: Number of rules to skip before returning results.
        include_archived: When true, include archived rules and archived parent
            regulations.

    Returns:
        Rule records serialized with the public API response schema.

    Raises:
        HTTPException: If ``regulation_id`` is provided and no matching visible
            regulation exists.
    """
    rules_list = get_rules(
        session,
        regulation_id=regulation_id,
        limit=limit,
        offset=offset,
        include_archived=include_archived,
    )
    if rules_list is None:
        raise HTTPException(
            status_code=404, detail=f"Regulation does not exist: {regulation_id}"
        )

    return rules_list


@router.post("", status_code=201)
def post_new_rule_route(session: SessionDep, rule: RuleCreate) -> RuleOut:
    """Create a new rule record.

    Args:
        session: Database session provided by FastAPI dependency injection.
        rule: Rule details supplied in the request body.

    Returns:
        Created rule details serialized with the public API response schema.

    Raises:
        HTTPException: If the rule references a missing regulation or another
            integrity conflict prevents creation.
    """
    try:
        new_rule = post_new_rule(session, rule)

    except RuleRegulationNotFoundError as err:
        raise HTTPException(
            status_code=404,
            detail=f"Regulation {rule.regulation_id} does not exist.",
        ) from err

    except RuleIndexConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Rule index {rule.rule_index} already exists for "
                f"regulation {rule.regulation_id}."
            ),
        ) from err

    except RuleConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=f"Rule was not added: {rule}.",
        ) from err

    return RuleOut.model_validate(new_rule)


@router.post("/{rule_id}/archive", status_code=200)
def post_rule_archived_by_id_route(
    session: SessionDep,
    rule_id: Annotated[int, Path(ge=1)],
    archive_request: ArchiveRequest | None = None,
) -> RuleOut:
    """Archive one rule by ID."""
    archive_request = archive_request or ArchiveRequest()

    rule = post_rule_archived_by_id(session, rule_id, archive_request=archive_request)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule does not exist: {rule_id}.")

    return RuleOut.model_validate(rule)


@router.post("/{rule_id}/restore", status_code=200)
def post_rule_restored_by_id_route(
    session: SessionDep, rule_id: Annotated[int, Path(ge=1)]
) -> RuleOut:
    """Restore one archived rule by ID."""
    rule = post_rule_restored_by_id(session, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule does not exist: {rule_id}.")

    return RuleOut.model_validate(rule)
