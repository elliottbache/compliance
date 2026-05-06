import logging
from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from compliance.api.schemas import (
    CertificationAttachmentsOut,
    CertificationCreate,
    CertificationOut,
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
from compliance.services._helpers import _format_attachment, get_constraint_name

logger = logging.getLogger(__name__)


class CertificationConflictError(Exception):
    """Raised when a certification cannot be created because of existing data."""


class CertificationCertifierNotFoundError(CertificationConflictError):
    """Raised when a certification references a missing certifier."""


class CertificationRegulationNotFoundError(CertificationConflictError):
    """Raised when a certification references a missing regulation."""


class CertificationSiteNotFoundError(CertificationConflictError):
    """Raised when a certification references a missing site."""


def get_certifications(
    session: Session,
    site_id: int | None,
    open_only: bool,
    limit: int | None,
    offset: int,
) -> list[CertificationOut] | None:
    """Retrieve certifications with optional site and open-only filters.

    Args:
        session: Database session used to execute the certification query.
        site_id: Optional site ID used to restrict results to one site. When
            supplied, the site must exist.
        open_only: When true, only return certifications without a resolution
            date.
        limit: Maximum number of certifications to return. If ``None``, all
            certifications are returned.
        offset: Number of certifications to skip before returning results.

    Returns:
        Certification records serialized with the public API schema, or an
        empty list if no certifications match. Returns ``None`` when ``site_id``
        is supplied but no matching site exists.
    """
    stmt = select(Certification)

    if site_id is not None:
        if session.get(Site, site_id) is None:
            return None
        stmt = stmt.where(Certification.site_id == site_id)

    if open_only:
        stmt = stmt.where(Certification.resolution_date.is_(None))

    stmt = (
        stmt.order_by(
            Certification.regulation_id,
            Certification.inspection_date.desc(),
            Certification.id,
        )
        .limit(limit)
        .offset(offset)
    )

    certifications = session.execute(stmt).scalars().all()

    return [
        CertificationOut.model_validate(certification)
        for certification in certifications
    ]


def get_certification_by_id(
    certification_id: int, session: Session
) -> Certification | None:
    """Return one certification by primary key, or None when it does not exist."""
    return session.get(Certification, certification_id)


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
    return _format_certification_attachments(results)


def post_new_certification(
    certification: CertificationCreate, session: Session
) -> Certification:
    """Persist a new certification record.

    Args:
        certification: Certification creation data validated by the API layer.
        session: Database session used to add and commit the certification.

    Returns:
        The created Certification ORM object.

    Raises:
        CertificationCertifierNotFoundError: If the certifier ID does not exist.
        CertificationRegulationNotFoundError: If the regulation ID does not exist.
        CertificationSiteNotFoundError: If the site ID does not exist.
        CertificationConflictError: If another integrity conflict prevents the insert.
    """
    certification_dict = certification.model_dump()
    new_certification = Certification(**certification_dict)
    try:
        session.add(new_certification)
        session.commit()
    except IntegrityError as exc:
        session.rollback()

        constraint_name = get_constraint_name(exc)

        if constraint_name == "certifications_certifier_id_fkey":
            raise CertificationCertifierNotFoundError(
                certification.certifier_id
            ) from exc

        if constraint_name == "certifications_regulation_id_fkey":
            raise CertificationRegulationNotFoundError(
                certification.regulation_id
            ) from exc

        if constraint_name == "certifications_site_id_fkey":
            raise CertificationSiteNotFoundError(certification.site_id) from exc

        raise CertificationConflictError() from exc

    return new_certification


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
