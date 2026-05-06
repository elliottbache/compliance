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
from compliance.services._helpers import get_constraint_name


class FindingConflictError(Exception):
    """Raised when a finding cannot be created because of a data conflict."""


class FindingMissingError(Exception):
    """Raised when a finding cannot be created because of existing data."""


class FindingMissingSiteError(FindingMissingError):
    """Raised when a finding references a missing certifier."""


class FindingMissingCertificationError(FindingMissingError):
    """Raised when a finding references a missing regulation."""


class FindingMissingRuleError(FindingMissingError):
    """Raised when a finding references a missing site."""


class FindingMissingAttachmentError(FindingMissingError):
    """Raised when a finding references a missing site."""


class FindingAttachmentCertificationMismatchError(FindingMissingAttachmentError):
    """Raised when a linked finding belongs to another certification."""


def get_findings(
    session: Session,
    site_id: int | None,
    certification_id: int | None,
    rule_id: int | None,
    attachment_id: int | None,
    open_only: bool,
) -> list[FindingOut]:
    """Retrieve findings with optional site, rule, and open-status filters.

    Args:
        session: Database session used to execute the finding query.
        site_id: Optional site identifier used to limit findings to one site.
        rule_id: Optional rule identifier used to limit findings to one rule.
        open_only: When true, only return findings whose certification has no
            resolution date.

    Returns:
        Finding records serialized with certification, regulation, and rule
        context, or an empty list if no matching findings exist.
    """
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
    )
    if site_id is not None:
        if session.get(Site, site_id) is None:
            raise FindingMissingSiteError(site_id)
        stmt = stmt.where(Certification.site_id == site_id)

    if certification_id is not None:
        if session.get(Certification, certification_id) is None:
            raise FindingMissingCertificationError(certification_id)
        stmt = stmt.where(Certification.id == certification_id)

    if rule_id is not None:
        if session.get(Rule, rule_id) is None:
            raise FindingMissingRuleError(rule_id)
        stmt = stmt.where(Rule.id == rule_id)

    if attachment_id is not None:
        if session.get(Attachment, attachment_id) is None:
            raise FindingMissingAttachmentError(attachment_id)
        stmt = stmt.where(FindingAttachment.attachment_id == attachment_id)

    if open_only:
        stmt = stmt.where(Certification.resolution_date.is_(None))

    results = session.execute(stmt).mappings().all()

    return _format_findings(results)


def post_new_finding(finding: FindingCreate, session: Session) -> FindingOut:
    """Persist a new finding record.

    Args:
        finding: Finding creation data validated by the API layer.
        session: Database session used to add and commit the finding.

    Returns:
        The created Finding ORM object.

    Raises:
        FindingCertifierError: If the certifier ID does not exist.
        FindingRegulationError: If the regulation ID does not exist.
        FindingSiteError: If the site ID does not exist.
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

        constraint_name = get_constraint_name(exc)

        if constraint_name == "findings_certification_id_fkey":
            raise FindingMissingCertificationError(finding.certification_id) from exc

        if constraint_name == "findings_rule_id_fkey":
            raise FindingMissingRuleError(finding.rule_id) from exc

        raise FindingConflictError() from exc

    return finding_out


def _format_findings(finding_list: Sequence[Mapping]) -> list[FindingOut]:
    """Format finding query rows into public finding output records.

    Args:
        finding_list: Rows containing ``Finding``, ``Certification``,
            ``Regulation``, and ``Rule`` ORM objects.

    Returns:
        Finding records serialized with certification and rule context.

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
                }
            )
        )

    return attachments
