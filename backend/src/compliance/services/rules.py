from compliance.db.models import (
    Regulation,
    Rule,
)
from compliance.services.lifecycle import (
    archive_record_by_id,
    get_constraint_name,
    record_is_visible,
    restore_record_by_id,
)
from compliance.services.schemas import (
    ArchiveRequest,
    RuleCreate,
    RuleOut,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class RuleConflictError(Exception):
    """Raised when a rule cannot be created because of existing data."""


class RuleRegulationNotFoundError(RuleConflictError):
    """Raised when a rule references a missing regulation."""


class RuleIndexConflictError(RuleConflictError):
    """Raised when a rule index already exists for a regulation."""


def get_rules(
    session: Session,
    *,
    regulation_id: int | None,
    limit: int | None,
    offset: int,
    include_archived: bool = False,
) -> list[RuleOut] | None:
    """Retrieve rules with optional regulation filtering and pagination.

    Args:
        session: Database session used to execute the rule query.
        regulation_id: Optional regulation ID used to restrict results to one
            regulation. When supplied, the regulation must exist.
        limit: Maximum number of rules to return. If ``None``, all matching
            rules are returned.
        offset: Number of rules to skip before returning results.
        include_archived: When true, include archived rules and archived parent
            regulations in the results.

    Returns:
        Rule records serialized with the public API schema for visible rules
        whose parent regulations are also visible, or an empty list if no rules
        match. Returns ``None`` when ``regulation_id`` is supplied but no
        matching visible regulation exists.
    """
    stmt = select(Rule).join(Rule.rule_regulation_rel)
    if not include_archived:
        stmt = stmt.where(Rule.archived_at.is_(None))
        stmt = stmt.where(Regulation.archived_at.is_(None))

    if regulation_id is not None:
        regulation = session.get(Regulation, regulation_id)
        if not record_is_visible(regulation, include_archived):
            return None
        stmt = stmt.where(Rule.regulation_id == regulation_id)

    stmt = (
        stmt.order_by(
            Rule.regulation_id,
            Rule.rule_index,
            Rule.id,
        )
        .limit(limit)
        .offset(offset)
    )

    rules = session.execute(stmt).scalars().all()

    return [RuleOut.model_validate(rule) for rule in rules]


def get_rule_by_id(
    session: Session, rule_id: int, *, include_archived: bool = True
) -> Rule | None:
    """Return one rule when it and its parent regulation are visible."""
    stmt = select(Rule).where(Rule.id == rule_id).join(Rule.rule_regulation_rel)
    if not include_archived:
        stmt = stmt.where(Rule.archived_at.is_(None))
        stmt = stmt.where(Regulation.archived_at.is_(None))

    return session.execute(stmt).scalar_one_or_none()


def post_new_rule(session: Session, rule: RuleCreate) -> Rule:
    """Persist a new rule record.

    Args:
        session: Database session used to add and commit the rule.
        rule: Rule creation data validated by the API layer.

    Returns:
        The created Rule ORM object.

    Raises:
        RuleRegulationNotFoundError: If the regulation ID does not exist.
        RuleIndexConflictError: If the rule index already exists for the
            regulation.
        RuleConflictError: If another integrity conflict prevents the insert.
    """
    rule_dict = rule.model_dump()
    new_rule = Rule(**rule_dict)
    try:
        session.add(new_rule)
        session.commit()
    except IntegrityError as exc:
        session.rollback()

        constraint_name = get_constraint_name(exc)

        if constraint_name == "fk_rules_regulation_id_regulations":
            raise RuleRegulationNotFoundError(rule.regulation_id) from exc

        if constraint_name == "uq_rules_regulation_id_rule_index":
            raise RuleIndexConflictError(rule.rule_index) from exc

        raise RuleConflictError() from exc

    return new_rule


def post_rule_archived_by_id(
    session: Session, rule_id: int, *, archive_request: ArchiveRequest
) -> Rule | None:
    """Archive a rule by ID.

    Args:
        session: Database session used to retrieve and update the rule.
        rule_id: Primary key for the rule to archive.
        archive_request: Archive metadata containing an optional reason.

    Returns:
        The rule ORM object, or ``None`` if no matching rule exists.
    """
    return archive_record_by_id(session, Rule, rule_id, archive_request)


def post_rule_restored_by_id(session: Session, rule_id: int) -> Rule | None:
    """Restore an archived rule by ID.

    Args:
        session: Database session used to retrieve and update the rule.
        rule_id: Primary key for the rule to restore.

    Returns:
        The rule ORM object, or ``None`` if no matching rule exists.
    """
    return restore_record_by_id(session, Rule, rule_id)
