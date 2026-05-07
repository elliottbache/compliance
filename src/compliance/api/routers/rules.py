from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    RuleCreate,
    RuleOut,
)
from compliance.services.rules import (
    RuleConflictError,
    RuleIndexConflictError,
    RuleRegulationNotFoundError,
    get_rule_by_id,
    get_rules,
    post_new_rule,
)

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


@router.get("/{rule_id}")
def get_rule_by_id_route(
    rule_id: int,
    session: SessionDep,
    include_archived: Annotated[bool, Query()] = False,
) -> RuleOut:
    """Return one rule by ID.

    Args:
        rule_id: Unique identifier for the rule to retrieve.
        session: Database session provided by FastAPI dependency injection.
        include_archived: When true, return archived rules and archived parent
            regulations.

    Returns:
        Rule details serialized with the public API response schema.

    Raises:
        HTTPException: If no visible rule exists for the requested ID.
    """
    rule = get_rule_by_id(rule_id, session, include_archived=include_archived)
    if rule is None:
        raise HTTPException(
            status_code=404,
            detail=f"No rule for this id found: {rule_id}",
        )

    return RuleOut.model_validate(rule)


@router.post("", status_code=201)
def post_new_rule_route(rule: RuleCreate, session: SessionDep) -> RuleOut:
    """Create a new rule record.

    Args:
        rule: Rule details supplied in the request body.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Created rule details serialized with the public API response schema.

    Raises:
        HTTPException: If the rule references a missing regulation or another
            integrity conflict prevents creation.
    """
    try:
        new_rule = post_new_rule(rule, session)

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
