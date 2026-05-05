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
)
from compliance.services._helpers import _format_attachment

logger = logging.getLogger(__name__)


def get_certifications(
    session: Session, limit: int | None, offset: int
) -> list[CertificationOut]:
    """Retrieve certifications ordered by regulation, inspection date, and ID.

    Args:
        session: Database session used to execute the certification query.
        limit: Maximum number of certifications to return. If ``None``, all
            certifications are returned.
        offset: Number of certifications to skip before returning results.

    Returns:
        Certification records serialized with the public API schema, or an
        empty list if no certifications exist.
    """
    stmt = (
        select(Certification)
        .order_by(
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
) -> Certification | None:
    """Persist a new certification record.

    Args:
        certification: Certification creation data validated by the API layer.
        session: Database session used to add and commit the certification.

    Returns:
        The created Certification ORM object, or ``None`` if an integrity conflict
        prevents the insert.

    """
    certification_dict = certification.model_dump()
    new_certification = Certification(**certification_dict)
    try:
        session.add(new_certification)
        session.commit()
    except IntegrityError as e:
        logger.error(f"Certification post error: {e}")
        session.rollback()
        return None

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
