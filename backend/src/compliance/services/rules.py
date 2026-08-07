"""Rule service functions for listing, creation, archive, and restore."""

from compliance.db.models import (
    AuditAction,
    AuditTargetType,
    Regulation,
    Rule,
)
from compliance.services.audit import record_audit_event
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
    UserOut,
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


def post_new_rule(session: Session, rule: RuleCreate) -> Rule:
    """Persist a new rule record.

    Parent validation checks that the regulation exists, not whether the
    regulation is visible in default archive-aware reads. This allows
    bookkeeping entries under archived regulations.

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
            raise RuleRegulationNotFoundError(
                f"Regulation {rule.regulation_id} does not exist."
            ) from exc

        if constraint_name == "uq_rules_regulation_id_rule_index":
            raise RuleIndexConflictError(
                f"Rule with regulation {rule.regulation_id} and index "
                f"{rule.rule_index} already exists."
            ) from exc

        raise RuleConflictError(f"Rule was not added: {rule}.") from exc

    return new_rule


def post_rule_archived_by_id(
    session: Session,
    rule_id: int,
    *,
    archive_request: ArchiveRequest,
    actor: UserOut | None = None,
) -> Rule | None:
    """Archive a rule by ID.

    Args:
        session: Database session used to retrieve and update the rule.
        rule_id: Primary key for the rule to archive.
        archive_request: Archive metadata containing an optional reason.
        actor: Optional authenticated user responsible for the archive action.
            When provided, a ``record.archived`` audit event is written in the
            same transaction.

    Returns:
        The rule ORM object, or ``None`` if no matching rule exists.

    Side effects:
        Archives the rule, records ``record.archived`` when ``actor`` is
        provided, and commits the session when the rule changes.
    """
    result = archive_record_by_id(session, Rule, rule_id, archive_request)
    if result.record is None:
        return None

    if result.changed:
        if actor is not None:
            record_audit_event(
                session,
                action=AuditAction.RECORD_ARCHIVED,
                target_type=AuditTargetType.RECORD,
                target_id=rule_id,
                actor_user_id=actor.id,
                actor_email=actor.email,
                context={
                    "record_type": "rule",
                    "rule_id": rule_id,
                    "regulation_id": result.record.regulation_id,
                    "archive_reason": result.record.archive_reason,
                },
            )
        session.commit()

    return result.record


def post_rule_restored_by_id(
    session: Session, rule_id: int, *, actor: UserOut | None = None
) -> Rule | None:
    """Restore an archived rule by ID.

    Args:
        session: Database session used to retrieve and update the rule.
        rule_id: Primary key for the rule to restore.
        actor: Optional authenticated user responsible for the restore action.
            When provided, a ``record.restored`` audit event is written in the
            same transaction.

    Returns:
        The rule ORM object, or ``None`` if no matching rule exists.

    Side effects:
        Restores the rule, records ``record.restored`` when ``actor`` is
        provided, and commits the session when the rule changes.
    """
    result = restore_record_by_id(session, Rule, rule_id)
    if result.record is None:
        return None

    if result.changed:
        if actor is not None:
            record_audit_event(
                session,
                action=AuditAction.RECORD_RESTORED,
                target_type=AuditTargetType.RECORD,
                target_id=rule_id,
                actor_user_id=actor.id,
                actor_email=actor.email,
                context={
                    "record_type": "rule",
                    "rule_id": rule_id,
                    "regulation_id": result.record.regulation_id,
                },
            )
        session.commit()

    return result.record
