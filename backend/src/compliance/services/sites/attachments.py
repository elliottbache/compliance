from collections.abc import Mapping, Sequence

from compliance.db.models import (
    Attachment,
    Certification,
    Client,
    Finding,
    FindingAttachment,
    Regulation,
    Rule,
    Site,
)
from compliance.services.attachments.formatting import format_attachment
from compliance.services.lifecycle import record_is_visible
from compliance.services.schemas import SiteAttachmentsOut
from compliance.services.sites.crud import SiteClientNotFoundError, SiteNotFoundError
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_site_attachments(
    session: Session, site_id: int, *, include_archived: bool = False
) -> SiteAttachmentsOut:
    """Retrieve attachment records for a site with certification and finding context.

    Args:
        session: Database session used to execute the attachment query.
        site_id: Unique identifier of the site whose attachments should be
            retrieved.
        include_archived: When true, include archived site, certification,
            attachment, regulation, rule, and finding records. By default,
            archived finding and rule rows are omitted from optional link
            context without hiding otherwise visible attachments.

    Returns:
        A formatted attachment collection for the visible site.

    Raises:
        SiteNotFoundError if the site id doesn't correspond to any visible ID.
        SiteClientNotFoundError if the site NIF doesn't correspond to any visible NIF.
    """
    site = session.get(Site, site_id)
    if site is None or not record_is_visible(site, include_archived):
        raise SiteNotFoundError(site_id)

    client = session.get(Client, site.nif)
    if not record_is_visible(client, include_archived):
        raise SiteClientNotFoundError(site.nif)

    finding_join_condition = (Finding.id == FindingAttachment.finding_id) & (
        Finding.certification_id == FindingAttachment.certification_id
    )
    rule_join_condition = Rule.id == Finding.rule_id
    if not include_archived:
        finding_join_condition = finding_join_condition & Finding.archived_at.is_(None)
        rule_join_condition = rule_join_condition & Rule.archived_at.is_(None)

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
        .outerjoin(
            FindingAttachment,
            (FindingAttachment.attachment_id == Attachment.id)
            & (FindingAttachment.certification_id == Attachment.certification_id),
        )
        .outerjoin(Finding, finding_join_condition)
        .outerjoin(Rule, rule_join_condition)
    )
    if not include_archived:
        stmt = stmt.where(Certification.archived_at.is_(None))
        stmt = stmt.where(Attachment.archived_at.is_(None))
        stmt = stmt.where(Regulation.archived_at.is_(None))

    stmt = stmt.order_by(Attachment.id, Finding.id)

    results = session.execute(stmt).mappings().all()
    if not results:
        return SiteAttachmentsOut(site_id=site_id, attachments=[])

    return _format_site_attachments(results)


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
        format_attachment(rows) for rows in rows_by_attachment.values()
    ]

    return SiteAttachmentsOut(
        site_id=first_row["Certification"].site_id, attachments=formatted_attachments
    )
