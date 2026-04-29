from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from compliance.api.schemas import ClientInfo, SiteAttachments
from compliance.db.models import (
    Attachment,
    Certification,
    Certifier,
    Finding,
    FindingAttachment,
    Regulation,
    Rule,
    Site,
)
from compliance.schemas import CertificationHistory, FindingHistory, SiteHistory


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
) -> SiteAttachments | None:
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


def post_new_client(client: ClientInfo, session: Session) -> ClientInfo | None:
    """Persist a new client record.

    Args:
        client: Client data validated by the API layer.
        session: Database session used to add and commit the client.

    Returns:
        The created client ORM object, or ``None`` if an integrity conflict
        prevents the insert.
    """
    client_dict = client.model_dump()
    new_client = ClientInfo(**client_dict)
    try:
        session.add(new_client)
        session.commit()
    except IntegrityError:
        session.rollback()
        return None

    return new_client


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

    site_history = {"site_id": first_row["site_id"], "certifications": list()}
    for row in site_history_rows:
        # add new dict to certifications dict with cert_id as key
        cert_idx = _find_cert_index(row["cert_id"], site_history["certifications"])
        if cert_idx is None:
            cert_dict = {
                "cert_id": row["cert_id"],
                "result": row["result"],
                "resolution_date": row["resolution_date"],
                "reg_title": row["reg_title"],
                "reg_description": row["reg_description"],
                "certifier_org_name": row["certifier_org_name"],
                "inspection_date": row["inspection_date"],
            }
            if row["finding_id"] is not None:
                cert_dict["findings"] = [_build_finding_history_from_site_history(row)]
            else:
                cert_dict["findings"] = []

            site_history["certifications"].append(
                CertificationHistory.model_validate(cert_dict)
            )

        # add new dict to findings list
        else:
            if row["finding_id"] is None:
                continue

            # find matching list item in certifications for cert_id
            cert_idx = _find_cert_index(row["cert_id"], site_history["certifications"])
            if cert_idx is None:
                raise KeyError(
                    f"Certification list item does not exist: cert_id = "
                    f"{row['cert_id']} in {site_history['certifications']}"
                )

            site_history["certifications"][cert_idx].findings.append(
                _build_finding_history_from_site_history(row)
            )

    site_history["inspection_count"] = len(site_history["certifications"])
    if site_history["inspection_count"] > 0:
        site_history["latest_inspection_date"] = site_history["certifications"][
            -1
        ].inspection_date

    return SiteHistory(**site_history)


def _find_cert_index(
    cert_id: int, site_history_cert_list: list[CertificationHistory]
) -> int | None:
    """Returns the index of the certification with the given cert_id, or None if absent."""
    idx = 0
    while (
        idx < len(site_history_cert_list)
        and site_history_cert_list[idx].cert_id != cert_id
    ):
        idx += 1

    return idx if idx < len(site_history_cert_list) else None


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
) -> SiteAttachments:
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

    first_row = next(iter(site_attachment_list))
    if not first_row:
        raise ValueError(f"First attachment row is empty: {site_attachment_list}")

    attachment_ids = set()
    site_attachments = {
        "site_id": first_row["Certification"].site_id,
        "attachments": list(),
    }
    for row in site_attachment_list:
        if row["Finding"] is not None:
            finding_links = [_build_finding_history_from_site_attachments(row)]
        else:
            finding_links = []

        if row["Attachment"].id not in attachment_ids:
            attachment_ids.add(row["Attachment"].id)

            # add new dict with attachment data
            attachment_dict = {
                "id": row["Attachment"].id,
                "file_type": row["Attachment"].file_type,
                "file_path": row["Attachment"].file_path,
                "description": row["Attachment"].description,
                "uploaded_at": row["Attachment"].uploaded_at,
                "certification_id": row["Attachment"].certification_id,
                "inspection_date": row["Certification"].inspection_date,
                "regulation_id": row["Certification"].regulation_id,
                "regulation_title": row["Regulation"].title,
                "finding_links": finding_links,
            }
            site_attachments["attachments"].append(attachment_dict)

        else:
            idx = _find_attachment_index(
                row["Attachment"].id, site_attachments["attachments"]
            )
            if idx is None:
                raise LookupError(
                    f"Attachment with id {row['Attachment'].id} is not found in site_attachments."
                )
            if row["Finding"] is not None:
                site_attachments["attachments"][idx]["finding_links"].append(
                    _build_finding_history_from_site_attachments(row)
                )

    return SiteAttachments(**site_attachments)


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


def _find_attachment_index(
    attachment_id: int, site_attachment_list: list[dict[str, Any]]
) -> int | None:
    """Returns the index of the attachment with the given attachment_id, or None if absent."""
    idx = 0
    while (
        idx < len(site_attachment_list)
        and site_attachment_list[idx]["id"] != attachment_id
    ):
        idx += 1

    return idx if idx < len(site_attachment_list) else None


if __name__ == "__main__":

    from compliance.db.db_access import get_db

    session = get_db()

    print(f"\nsite 71: {get_site_history_by_id(71, next(iter(session)))}")

    session = get_db()
    print(f"\nsite 71: {get_site_attachments_by_id(71, next(iter(session)))}")
