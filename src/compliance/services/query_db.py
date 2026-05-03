import logging
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from compliance.api.schemas import (
    AttachmentCreate,
    AttachmentOut,
    AttachmentWithContextOut,
    CertificationAttachmentsOut,
    ClientInOut,
    FindingOut,
    SiteAttachmentsOut,
)
from compliance.db.models import (
    Attachment,
    Certification,
    Certifier,
    Client,
    Finding,
    FindingAttachment,
    Regulation,
    Rule,
    Site,
)
from compliance.schemas import CertificationHistory, FindingHistory, SiteHistory

logger = logging.getLogger(__name__)


class AttachmentCreateError(Exception):
    """Base error for attachment creation failures."""


class AttachmentCertificationNotFoundError(AttachmentCreateError):
    """Raised when an attachment's certification does not exist."""


class AttachmentFindingNotFoundError(AttachmentCreateError):
    """Raised when an attachment's linked finding does not exist."""


class AttachmentFindingCertificationMismatchError(AttachmentCreateError):
    """Raised when a linked finding belongs to another certification."""


class AttachmentConflictError(AttachmentCreateError):
    """Raised when attachment creation conflicts with stored data."""


def get_site_by_id(site_id: int, session: Session) -> Site | None:
    """Return one site by primary key, or None when it does not exist."""
    return session.get(Site, site_id)


def get_certification_by_id(
    certification_id: int, session: Session
) -> Certification | None:
    """Return one certification by primary key, or None when it does not exist."""
    return session.get(Certification, certification_id)


def get_site_history_by_id(site_id: int, session: Session) -> SiteHistory | None:
    """Retrieve the certification history for a site.

    Queries certification records for the given site using the provided session,
    joins related regulation, certifier, finding, and rule data, and converts
    the result into a site-history value ordered by inspection date.

    Args:
        site_id: Unique identifier of the site whose certification history
            should be retrieved.

    Returns:
        A formatted site history containing certification and related
        compliance details, or ``None`` if no matching records exist.
    """

    # perform query
    stmt = (
        select(
            Certification.site_id,
            Certification.id.label("cert_id"),
            Certification.result,
            Certification.resolution_date,
            Certification.inspection_date,
            Regulation.title.label("reg_title"),
            Regulation.description.label("reg_description"),
            Certifier.organization_name.label("certifier_org_name"),
            Finding.id.label("finding_id"),
            Finding.finding,
            Rule.rule_index,
            Rule.title.label("rule_title"),
            Rule.description.label("rule_description"),
        )
        .where(Certification.site_id == site_id)
        .join(Certification.certification_regulation_rel)
        .join(Certification.certification_certifier_rel)
        .outerjoin(Certification.certification_finding_rel)
        .outerjoin(Finding.finding_rule_rel)
        .order_by(Certification.inspection_date)
    )
    results = session.execute(stmt).mappings().all()
    if not results:
        return None
    return _format_site_history(results)


def get_site_attachments_by_id(
    site_id: int, session: Session
) -> SiteAttachmentsOut | None:
    """Retrieve attachment records for a site with certification and finding context.

    Args:
        site_id: Unique identifier of the site whose attachments should be
            retrieved.
        session: Database session used to execute the attachment query.

    Returns:
        A formatted attachment collection for the site, or ``None`` if no
        matching attachment records exist.
    """
    stmt = (
        select(
            Attachment,
            Certification,
            Regulation,
            FindingAttachment,
            Finding,
            Rule,
        )
        .where(Certification.site_id == site_id)
        .join(Attachment.attachment_certification_rel)
        .join(Certification.certification_regulation_rel)
        .outerjoin(Attachment.attachment_finding_attachment_rel)
        .outerjoin(FindingAttachment.finding_attachment_finding_rel)
        .outerjoin(Finding.finding_rule_rel)
    )
    results = session.execute(stmt).mappings().all()
    if not results:
        return None
    return _format_site_attachments(results)


def get_certifications_by_site_id(
    site_id: int, session: Session, limit: int | None, offset: int
) -> list[Certification]:
    """Retrieve certifications for one site ordered by latest resolution date.

    Args:
        site_id: Unique identifier of the site whose certifications should be
            retrieved.
        session: Database session used to execute the certification query.
        limit: Maximum number of certifications to return. If ``None``, all
            matching certifications are returned.
        offset: Number of matching certifications to skip before returning
            results.

    Returns:
        A list of certification ORM objects ordered by resolution date
        descending and then ID, or [] if no matching certifications exist.
    """
    stmt = (
        select(Certification)
        .where(Certification.site_id == site_id)
        .order_by(Certification.resolution_date.desc(), Certification.id)
        .limit(limit)
        .offset(offset)
    )
    return list(session.execute(stmt).scalars().all())


def get_certification_attachments_by_id(
    certification_id: int, session: Session
) -> CertificationAttachmentsOut | None:
    """Retrieve attachment records for one certification.

    Checks that the certification exists before querying its attachments so a
    missing certification can be distinguished from an existing certification
    with no attachment records.

    Args:
        certification_id: Unique identifier of the certification whose
            attachments should be retrieved.
        session: Database session used to check the certification and execute
            the attachment query.

    Returns:
        A formatted attachment collection for the certification, an empty
        attachment collection if the certification exists without attachments,
        or ``None`` if no matching certification exists.
    """
    # check if certification exists
    certification = session.get(Certification, certification_id)
    if certification is None:
        return None

    # get attachments for certification
    stmt = (
        select(
            Attachment,
            Certification,
            Regulation,
            FindingAttachment,
            Finding,
            Rule,
        )
        .where(Certification.id == certification_id)
        .join(Attachment.attachment_certification_rel)
        .join(Certification.certification_regulation_rel)
        .outerjoin(Attachment.attachment_finding_attachment_rel)
        .outerjoin(FindingAttachment.finding_attachment_finding_rel)
        .outerjoin(Finding.finding_rule_rel)
        .order_by(Attachment.id, Finding.id)
    )
    results = session.execute(stmt).mappings().all()
    if results == []:
        return CertificationAttachmentsOut.model_validate(
            {"certification_id": certification_id, "attachments": []}
        )
    else:
        return _format_certification_attachments(results)


def get_findings(
    session: Session, site_id: int | None, rule_id: int | None, open_only: bool
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
        select(
            Finding,
            Certification,
            Regulation,
            Rule,
        )
        .join(Finding.finding_certification_rel)
        .join(Certification.certification_regulation_rel)
        .join(Finding.finding_rule_rel)
    )
    if site_id is not None:
        stmt = stmt.where(Certification.site_id == site_id)
    if rule_id is not None:
        stmt = stmt.where(Rule.id == rule_id)
    if open_only:
        stmt = stmt.where(Certification.resolution_date.is_(None))

    results = session.execute(stmt).mappings().all()

    return _format_findings(results)


def get_attachment_by_id(
    attachment_id: int, session: Session
) -> AttachmentWithContextOut | None:
    """Retrieve one attachment with certification, regulation, and finding context.

    Args:
        attachment_id: Unique identifier of the attachment to retrieve.
        session: Database session used to execute the attachment query.

    Returns:
        A formatted attachment response containing certification, regulation,
        and linked finding context, or ``None`` if no matching attachment exists.
    """
    stmt = (
        select(
            Attachment,
            Certification,
            Regulation,
            FindingAttachment,
            Finding,
            Rule,
        )
        .where(Attachment.id == attachment_id)
        .join(Attachment.attachment_certification_rel)
        .join(Certification.certification_regulation_rel)
        .outerjoin(Attachment.attachment_finding_attachment_rel)
        .outerjoin(FindingAttachment.finding_attachment_finding_rel)
        .outerjoin(Finding.finding_rule_rel)
    )
    rows = session.execute(stmt).mappings().all()
    return None if not rows else _format_attachment(rows)


def post_new_client(client: ClientInOut, session: Session) -> Client | None:
    """Persist a new client record.

    Args:
        client: Client data validated by the API layer.
        session: Database session used to add and commit the client.

    Returns:
        The created Client ORM object, or ``None`` if an integrity conflict
        prevents the insert.

    """
    client_dict = client.model_dump()
    new_client = Client(**client_dict)
    try:
        session.add(new_client)
        session.commit()
    except IntegrityError:
        session.rollback()
        return None

    return new_client


def post_new_attachment(
    attachment: AttachmentCreate, session: Session
) -> AttachmentOut:
    """Persist a new attachment metadata record and optional finding links.

    Builds temporary storage metadata for the attachment, validates that the
    parent certification and requested linked findings exist, and creates any
    finding-attachment link rows in the same transaction.

    Args:
        attachment: Attachment metadata validated by the API layer.
        session: Database session used to validate related records and persist
            the attachment metadata.

    Returns:
        The created attachment metadata with certification and regulation
        context.

    Raises:
        AttachmentCertificationNotFoundError: If the parent certification does
            not exist.
        AttachmentFindingNotFoundError: If a requested linked finding does not
            exist.
        AttachmentFindingCertificationMismatchError: If a requested finding
            belongs to another certification.
        AttachmentConflictError: If the attachment or link rows conflict with
            existing stored data.
    """
    attachment_dict = attachment.model_dump()
    orm_data = {
        "file_type": attachment.file_type,
        "certification_id": attachment.certification_id,
        "description": attachment.description,
        "file_path": "/path/placeholder/"
        + attachment_dict["file_name"]
        + "."
        + attachment_dict["file_type"],
        "uploaded_at": date.today(),
    }
    new_attachment = Attachment(**orm_data)

    # check if certification exists
    certification = session.get(Certification, attachment.certification_id)
    if certification is None:
        raise AttachmentCertificationNotFoundError(
            f"Certification {attachment.certification_id} does not exist."
        )

    # check if findings exist
    for finding_id in attachment.finding_ids:
        finding = session.get(Finding, finding_id)
        if finding is None:
            raise AttachmentFindingNotFoundError(
                f"Finding {finding_id} does not exist."
            )

        if finding.certification_id != attachment.certification_id:
            raise AttachmentFindingCertificationMismatchError(
                f"Finding {finding_id} does not belong to certification "
                f"{attachment.certification_id}."
            )

    try:
        # add new attachment
        session.add(new_attachment)
        session.flush()

        # add new findingAttachment
        for finding_id in attachment.finding_ids:
            new_finding_attachment = FindingAttachment(
                finding_id=finding_id,
                attachment_id=new_attachment.id,
                certification_id=attachment.certification_id,
            )
            session.add(new_finding_attachment)
        session.flush()

        new_attachment_with_context = _format_new_attachment_with_context(
            new_attachment,
            certification,
            attachment.finding_ids,
        )
        session.commit()

    except IntegrityError as e:
        logger.warning(f"Error posting new attachment: {e}")
        session.rollback()
        raise AttachmentConflictError("Attachment could not be created.") from e

    except Exception:
        session.rollback()
        raise

    return AttachmentOut.model_validate(new_attachment_with_context)


def _format_new_attachment_with_context(
    attachment: Attachment,
    certification: Certification,
    finding_ids: list[int],
) -> AttachmentOut:
    """Build output metadata for a newly created attachment.

    Args:
        attachment: Newly persisted attachment ORM object.
        certification: Parent certification for the attachment.
        finding_ids: Finding IDs linked to the attachment during creation.

    Returns:
        Attachment metadata enriched with certification and regulation context.
    """
    file_name = Path(attachment.file_path).stem
    return AttachmentOut(
        id=attachment.id,
        file_type=attachment.file_type,
        certification_id=attachment.certification_id,
        description=attachment.description,
        uploaded_at=attachment.uploaded_at,
        file_name=file_name,
        finding_ids=list(finding_ids),
        inspection_date=certification.inspection_date,
        regulation_id=certification.regulation_id,
        regulation_title=certification.certification_regulation_rel.title,
    )


def _format_site_history(site_history_rows: Sequence[Mapping]) -> SiteHistory:
    """Aggregate site history rows into a certification-oriented structure.

    Groups rows by certification and collects related findings under each
    certification entry. Also records the total number of inspections and the
    most recent inspection date from the aggregated result.

    Args:
        site_history_rows: A sequence of row mappings representing site history
            records.

    Returns:
        A Site object containing the aggregated site history summary.

    Raises:
        StopIteration: If ``site_history_rows`` is empty.
        ValueError: If the first row is empty.
        KeyError: If required row fields are missing or a certification lookup
            fails unexpectedly during aggregation.
    """

    first_row = next(iter(site_history_rows))
    if not first_row:
        raise ValueError(f"First site history row is empty: {site_history_rows}")

    certifications_by_id: dict[int, CertificationHistory] = {}
    site_history = {"site_id": first_row["site_id"], "certifications": list()}
    for row in site_history_rows:
        cert_id = row["cert_id"]
        certification = certifications_by_id.get(cert_id)

        if certification is None:
            cert_dict = {
                "cert_id": cert_id,
                "result": row["result"],
                "resolution_date": row["resolution_date"],
                "reg_title": row["reg_title"],
                "reg_description": row["reg_description"],
                "certifier_org_name": row["certifier_org_name"],
                "inspection_date": row["inspection_date"],
                "findings": [],
            }
            certification = CertificationHistory.model_validate(cert_dict)
            certifications_by_id[cert_id] = certification
            site_history["certifications"].append(certification)

        if row["finding_id"] is not None:
            certification.findings.append(_build_finding_history_from_site_history(row))

    site_history["inspection_count"] = len(site_history["certifications"])
    if site_history["inspection_count"] > 0:
        site_history["latest_inspection_date"] = site_history["certifications"][
            -1
        ].inspection_date

    return SiteHistory(**site_history)


def _build_finding_history_from_site_history(row: Mapping) -> FindingHistory:
    """Build a Finding from the selected fields in a site history row."""
    keys = ["finding_id", "finding", "rule_index", "rule_title", "rule_description"]

    missing_keys = [key for key in keys if key not in row]
    if missing_keys:
        raise KeyError(
            "Missing finding fields in row: "
            f"{missing_keys}. Row keys: {sorted(row.keys())}"
        )
    finding = {k: row[k] for k in keys}

    return FindingHistory.model_validate(finding)


def _format_site_attachments(
    site_attachment_list: Sequence[Mapping],
) -> SiteAttachmentsOut:
    """Aggregate attachment query rows into a site-level attachment response.

    Groups rows by attachment and collects linked findings under each attachment
    so repeated attachment rows do not produce duplicate attachment records.

    Args:
        site_attachment_list: Rows from the site attachment query containing
            attachment, certification, regulation, finding, link, and rule
            objects.

    Returns:
        A site attachment response containing unique attachments and their
        finding links.

    Raises:
        StopIteration: If ``site_attachment_list`` is empty.
        ValueError: If the first attachment row is empty.
    """

    it = iter(site_attachment_list)
    try:
        first_row = next(it)
    except StopIteration:
        raise StopIteration("site_attachment_list is empty") from None

    if not first_row:
        raise ValueError(f"First attachment row is empty: {site_attachment_list}")

    # 1. Group all rows by their Attachment ID
    rows_by_attachment: dict[int, list[Mapping]] = {}
    for row in site_attachment_list:
        aid = row["Attachment"].id
        if aid not in rows_by_attachment:
            rows_by_attachment[aid] = []
        rows_by_attachment[aid].append(row)

    # 2. Process each group using the single-attachment formatter
    # We maintain the order of appearance by iterating over the original list
    # or just use the grouped values.
    formatted_attachments = [
        _format_attachment(rows) for rows in rows_by_attachment.values()
    ]

    return SiteAttachmentsOut(
        site_id=first_row["Certification"].site_id, attachments=formatted_attachments
    )


def _format_certification_attachments(
    certification_attachment_list: Sequence[Mapping],
) -> CertificationAttachmentsOut:
    """Aggregate attachment query rows into a certification-level response.

    Groups rows by attachment and collects linked findings under each
    attachment so repeated attachment rows do not produce duplicate attachment
    records.

    Args:
        certification_attachment_list: Rows from the certification attachment
            query containing attachment, certification, regulation, finding,
            link, and rule objects.

    Returns:
        A certification attachment response containing unique attachments and
        their finding links.

    Raises:
        StopIteration: If ``certification_attachment_list`` is empty.
        ValueError: If the first attachment row is empty.
    """

    it = iter(certification_attachment_list)
    try:
        first_row = next(it)
    except StopIteration:
        raise StopIteration("certification_attachment_list is empty") from None

    if not first_row:
        raise ValueError(
            f"First attachment row is empty: {certification_attachment_list}"
        )

    # 1. Group all rows by their Attachment ID
    rows_by_attachment: dict[int, list[Mapping]] = {}
    for row in certification_attachment_list:
        aid = row["Attachment"].id
        if aid not in rows_by_attachment:
            rows_by_attachment[aid] = []
        rows_by_attachment[aid].append(row)

    # 2. Process each group using the single-attachment formatter
    # We maintain the order of appearance by iterating over the original list
    # or just use the grouped values.
    formatted_attachments = [
        _format_attachment(rows) for rows in rows_by_attachment.values()
    ]

    return CertificationAttachmentsOut(
        certification_id=first_row["Certification"].id,
        attachments=formatted_attachments,
    )


def _format_attachment(
    rows: Sequence[Mapping],
) -> AttachmentWithContextOut:
    """Aggregate query rows for a single attachment into an attachment response.

    Args:
        rows: Rows for one attachment containing attachment, certification,
            regulation, finding-link, finding, and rule objects.

    Returns:
        A single attachment response with linked findings collected under
        ``finding_links``.
    """
    attachment_dict: dict[str, Any] = dict()
    for row in rows:
        attachment_id = row["Attachment"].id
        if not attachment_dict:
            attachment_dict = {
                "id": attachment_id,
                "file_type": row["Attachment"].file_type,
                "file_path": row["Attachment"].file_path,
                "description": row["Attachment"].description,
                "uploaded_at": row["Attachment"].uploaded_at,
                "certification_id": row["Attachment"].certification_id,
                "inspection_date": row["Certification"].inspection_date,
                "regulation_id": row["Certification"].regulation_id,
                "regulation_title": row["Regulation"].title,
                "finding_links": [],
            }

        if row["Finding"] is not None:
            attachment_dict["finding_links"].append(
                _build_finding_history_from_site_attachments(row)
            )

    return AttachmentWithContextOut(**attachment_dict)


def _build_finding_history_from_site_attachments(row: Mapping) -> FindingHistory:
    """Build finding history from a site-attachments query row."""
    field_sources = {
        "finding_id": ("Finding", "id"),
        "finding": ("Finding", "finding"),
        "rule_index": ("Rule", "rule_index"),
        "rule_title": ("Rule", "title"),
        "rule_description": ("Rule", "description"),
    }
    missing_keys = [
        field_name
        for field_name, (row_key, attr_name) in field_sources.items()
        if row_key not in row or not hasattr(row[row_key], attr_name)
    ]
    if missing_keys:
        raise KeyError(
            "Missing finding history fields in site attachment row: "
            f"{missing_keys}. Row keys: {sorted(row.keys())}"
        )

    finding_history = {
        field_name: getattr(row[row_key], attr_name)
        for field_name, (row_key, attr_name) in field_sources.items()
    }
    return FindingHistory.model_validate(finding_history)


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
    return [_build_finding_out(row) for row in finding_list]


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


if __name__ == "__main__":
    from compliance.db.db_access import get_db

    session = get_db()

    print(f"\nsite 71: {get_site_history_by_id(71, next(iter(session)))}")

    session = get_db()
    print(f"\nsite 71: {get_site_attachments_by_id(71, next(iter(session)))}")
