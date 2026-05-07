from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from compliance.api.schemas import (
    FindingAttachmentOut,
    FindingCreate,
    FindingOut,
)
from compliance.db.models import (
    Attachment,
    Certification,
    Finding,
    FindingAttachment,
    Regulation,
    Rule,
    Site,
)
from compliance.services._helpers import record_is_visible


class FindingConflictError(Exception):
    """Raised when a finding cannot be created because of a data conflict."""


class FindingMissingError(Exception):
    """Raised when a finding cannot be created because of existing data."""


class FindingMissingSiteError(FindingMissingError):
    """Raised when a finding query references a missing site."""


class FindingMissingCertificationError(FindingMissingError):
    """Raised when a finding references a missing certification."""


class FindingMissingRuleError(FindingMissingError):
    """Raised when a finding references a missing rule."""


class FindingMissingAttachmentError(FindingMissingError):
    """Raised when a finding references a missing attachment."""


class FindingAttachmentCertificationMismatchError(FindingMissingAttachmentError):
    """Raised when a linked finding belongs to another certification."""


def get_findings(
    session: Session,
    *,
    site_id: int | None,
    certification_id: int | None,
    rule_id: int | None,
    attachment_id: int | None,
    open_only: bool,
    include_archived: bool = False,
) -> list[FindingOut]:
    """Retrieve findings with optional filters and linked attachment context.

    Args:
        session: Database session used to execute the finding query.
        site_id: Optional site identifier used to limit findings to one site.
        certification_id: Optional certification identifier used to limit findings
            to one certification.
        rule_id: Optional rule identifier used to limit findings to one rule.
        attachment_id: Optional attachment identifier used to limit findings to one
            attachment.
        open_only: When true, only return findings whose certification has no
            resolution date.
        include_archived: When true, include archived findings and related
            certification, site, regulation, rule, and attachment context. By
            default, archived attachment rows are omitted from optional context
            without hiding otherwise visible findings.

    Returns:
        Finding records serialized with visible certification, regulation, rule,
        and optional attachment context. Returns an empty list if no matching
        visible findings exist.

    Raises:
        FindingMissingSiteError: If ``site_id`` is provided but no site exists.
        FindingMissingCertificationError: If ``certification_id`` is provided but
            no certification exists.
        FindingMissingRuleError: If ``rule_id`` is provided but no rule exists.
        FindingMissingAttachmentError: If ``attachment_id`` is provided but no
            attachment exists.
    """
    attachment_join_condition = (Attachment.id == FindingAttachment.attachment_id) & (
        Attachment.certification_id == FindingAttachment.certification_id
    )
    if not include_archived:
        attachment_join_condition = (
            attachment_join_condition & Attachment.archived_at.is_(None)
        )

    stmt = (
        select(Finding, Certification, Regulation, Rule, Attachment)
        .join(Finding.finding_certification_rel)
        .join(Certification.certification_site_rel)
        .join(Certification.certification_regulation_rel)
        .join(Finding.finding_rule_rel)
        .outerjoin(
            FindingAttachment,
            (FindingAttachment.finding_id == Finding.id)
            & (FindingAttachment.certification_id == Finding.certification_id),
        )
        .outerjoin(
            Attachment,
            attachment_join_condition,
        )
    )
    if not include_archived:
        stmt = stmt.where(Finding.archived_at.is_(None))
        stmt = stmt.where(Certification.archived_at.is_(None))
        stmt = stmt.where(Site.archived_at.is_(None))
        stmt = stmt.where(Regulation.archived_at.is_(None))
        stmt = stmt.where(Rule.archived_at.is_(None))

    if site_id is not None:
        site = session.get(Site, site_id)
        if not record_is_visible(site, include_archived):
            raise FindingMissingSiteError(site_id)
        stmt = stmt.where(Certification.site_id == site_id)

    if certification_id is not None:
        certification = session.get(Certification, certification_id)
        if not record_is_visible(certification, include_archived):
            raise FindingMissingCertificationError(certification_id)
        stmt = stmt.where(Certification.id == certification_id)

    if rule_id is not None:
        rule = session.get(Rule, rule_id)
        if not record_is_visible(rule, include_archived):
            raise FindingMissingRuleError(rule_id)
        stmt = stmt.where(Rule.id == rule_id)

    if attachment_id is not None:
        attachment = session.get(Attachment, attachment_id)
        if not record_is_visible(attachment, include_archived):
            raise FindingMissingAttachmentError(attachment_id)
        stmt = stmt.where(FindingAttachment.attachment_id == attachment_id)

    if open_only:
        stmt = stmt.where(Certification.resolution_date.is_(None))

    stmt = stmt.order_by(
        Certification.inspection_date.desc(),
        Finding.id,
        Attachment.id,
    )

    results = session.execute(stmt).mappings().all()

    return _format_findings(results)


def get_finding_by_id(
    finding_id: int, session: Session, *, include_archived: bool = False
) -> FindingOut | None:
    """Return one finding with context by primary key.

    Args:
        finding_id: Unique identifier of the finding to retrieve.
        session: Database session used to execute the finding query.
        include_archived: When true, return archived findings and related
            certification, site, regulation, rule, and attachment context. By
            default, archived attachment rows are omitted from optional context.

    Returns:
        Finding details serialized with visible certification, regulation, rule,
        and optional linked attachment context, or ``None`` when no matching
        visible finding exists.
    """
    attachment_join_condition = (Attachment.id == FindingAttachment.attachment_id) & (
        Attachment.certification_id == FindingAttachment.certification_id
    )
    if not include_archived:
        attachment_join_condition = (
            attachment_join_condition & Attachment.archived_at.is_(None)
        )

    stmt = (
        select(Finding, Certification, Regulation, Rule, Attachment)
        .join(Finding.finding_certification_rel)
        .join(Certification.certification_site_rel)
        .join(Certification.certification_regulation_rel)
        .join(Finding.finding_rule_rel)
        .outerjoin(
            FindingAttachment,
            (FindingAttachment.finding_id == Finding.id)
            & (FindingAttachment.certification_id == Finding.certification_id),
        )
        .outerjoin(
            Attachment,
            attachment_join_condition,
        )
        .where(Finding.id == finding_id)
    )
    if not include_archived:
        stmt = stmt.where(Finding.archived_at.is_(None))
        stmt = stmt.where(Certification.archived_at.is_(None))
        stmt = stmt.where(Site.archived_at.is_(None))
        stmt = stmt.where(Regulation.archived_at.is_(None))
        stmt = stmt.where(Rule.archived_at.is_(None))

    results = session.execute(stmt).mappings().all()
    findings = _format_findings(results)
    return findings[0] if findings else None


def post_new_finding(finding: FindingCreate, session: Session) -> FindingOut:
    """Persist a new finding record and optional attachment links.

    Args:
        finding: Finding creation data validated by the API layer.
        session: Database session used to add and commit the finding.

    Returns:
        The created finding serialized with certification, regulation, rule, and
        linked attachment context.

    Raises:
        FindingMissingCertificationError: If the certification ID does not exist.
        FindingMissingRuleError: If the rule ID does not exist.
        FindingMissingAttachmentError: If a linked attachment ID does not exist.
        FindingAttachmentCertificationMismatchError: If a linked attachment
            belongs to another certification.
        FindingConflictError: If another integrity conflict prevents the insert.
    """
    finding_dict = finding.model_dump(exclude={"attachment_ids"})
    new_finding = Finding(**finding_dict)
    attachment_ids = finding.attachment_ids

    # check if certification exists
    certification = session.get(Certification, finding.certification_id)
    if certification is None:
        raise FindingMissingCertificationError(
            f"Certification {finding.certification_id} does not exist."
        )

    # check if rule exists
    rule = session.get(Rule, finding.rule_id)
    if rule is None:
        raise FindingMissingRuleError(f"Rule {finding.rule_id} does not exist.")

    # check if attachments exist
    if finding.attachment_ids:
        for attachment_id in finding.attachment_ids:
            attachment = session.get(Attachment, attachment_id)
            if attachment is None:
                raise FindingMissingAttachmentError(
                    f"Attachment {attachment_id} does not exist."
                )

            if finding.certification_id != attachment.certification_id:
                raise FindingAttachmentCertificationMismatchError(
                    f"Attachment {attachment_id} does not belong to certification "
                    f"{finding.certification_id}."
                )

    try:
        session.add(new_finding)
        session.flush()

        if attachment_ids:
            # add new findingAttachment
            for attachment_id in attachment_ids:
                new_finding_attachment = FindingAttachment(
                    finding_id=new_finding.id,
                    attachment_id=attachment_id,
                    certification_id=finding.certification_id,
                )
                session.add(new_finding_attachment)
            session.flush()

        stmt = (
            select(Finding, Certification, Regulation, Rule, Attachment)
            .join(Finding.finding_certification_rel)
            .join(Certification.certification_regulation_rel)
            .join(Finding.finding_rule_rel)
            .outerjoin(
                FindingAttachment,
                (FindingAttachment.finding_id == Finding.id)
                & (FindingAttachment.certification_id == Finding.certification_id),
            )
            .outerjoin(
                Attachment,
                (Attachment.id == FindingAttachment.attachment_id)
                & (Attachment.certification_id == FindingAttachment.certification_id),
            )
            .where(Finding.id == new_finding.id)
        )
        results = session.execute(stmt).mappings().all()
        finding_out = _format_findings(results)[0]

        session.commit()

    except IntegrityError as exc:
        session.rollback()

        raise FindingConflictError() from exc

    return finding_out


def _format_findings(finding_list: Sequence[Mapping]) -> list[FindingOut]:
    """Format finding query rows into public finding output records.

    Args:
        finding_list: Rows containing ``Finding``, ``Certification``,
            ``Regulation``, ``Rule``, and optional ``Attachment`` ORM objects.

    Returns:
        Unique finding records serialized with certification, rule, and linked
        attachment context.

    Raises:
        KeyError: If required row objects or nested fields are missing.
    """
    rows_by_finding: dict[int, list[Mapping]] = {}
    for row in finding_list:
        finding_id = row["Finding"].id
        if finding_id not in rows_by_finding:
            rows_by_finding[finding_id] = []
        rows_by_finding[finding_id].append(row)

    formatted_findings: list[FindingOut] = []
    for rows in rows_by_finding.values():
        finding = _build_finding_out(rows[0])
        attachments = _build_finding_attachments(rows)
        formatted_findings.append(
            finding.model_copy(update={"attachments": attachments})
        )

    return formatted_findings


def _build_finding_out(row: Mapping) -> FindingOut:
    """Build a public finding output object from one finding query row."""
    field_sources = {
        "finding_id": ("Finding", "id"),
        "finding": ("Finding", "finding"),
        "site_id": ("Certification", "site_id"),
        "certification_id": ("Certification", "id"),
        "certification_resolution_date": ("Certification", "resolution_date"),
        "certification_title": ("Regulation", "title"),
        "rule_id": ("Rule", "id"),
        "rule_index": ("Rule", "rule_index"),
        "rule_title": ("Rule", "title"),
        "rule_description": ("Rule", "description"),
        "archived_at": ("Finding", "archived_at"),
        "archive_reason": ("Finding", "archive_reason"),
    }
    missing_fields = [
        field_name
        for field_name, (row_key, attr_name) in field_sources.items()
        if row_key not in row or not hasattr(row[row_key], attr_name)
    ]
    if missing_fields:
        raise KeyError(
            "Missing finding output fields in row: "
            f"{missing_fields}. Row keys: {sorted(row.keys())}"
        )

    finding_out = {
        field_name: getattr(row[row_key], attr_name)
        for field_name, (row_key, attr_name) in field_sources.items()
    }

    return FindingOut.model_validate(finding_out)


def _build_finding_attachments(rows: Sequence[Mapping]) -> list[FindingAttachmentOut]:
    """Build attachment summaries from rows for one finding."""
    attachments: list[FindingAttachmentOut] = []
    seen_attachment_ids: set[int] = set()
    for row in rows:
        attachment = row.get("Attachment")
        if attachment is None or attachment.id in seen_attachment_ids:
            continue

        seen_attachment_ids.add(attachment.id)
        attachments.append(
            FindingAttachmentOut.model_validate(
                {
                    "attachment_id": attachment.id,
                    "file_type": attachment.file_type,
                    "file_path": attachment.file_path,
                    "description": attachment.description,
                    "uploaded_at": attachment.uploaded_at,
                    "archived_at": attachment.archived_at,
                    "archive_reason": attachment.archive_reason,
                }
            )
        )

    return attachments
