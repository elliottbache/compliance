from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from compliance.api.schemas import (
    SiteAttachmentsOut,
    SiteCertificationsOut,
    SiteCreate,
)
from compliance.db.db_access import get_engine_metadata, get_tables
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
from compliance.services._helpers import (
    _format_attachment,
    get_constraint_name,
    record_is_visible,
)


class SiteConflictError(Exception):
    """Raised when a site cannot be created because of existing data."""


class SiteClientNotFoundError(SiteConflictError):
    """Raised when a site references a missing client."""


def get_sites(
    session: Session,
    *,
    nif: str | None,
    limit: int | None,
    offset: int,
    include_archived: bool = False,
) -> list[Site] | None:
    """Retrieve sites with optional client filtering.

    Args:
        session: Database session used to execute the site query.
        nif: Optional client NIF used to restrict results to one client. When
            supplied, the client must exist.
        limit: Maximum number of sites to return. If ``None``, all sites
            are returned.
        offset: Number of sites to skip before returning results.
        include_archived: When true, include archived sites in the results.

    Returns:
        Site ORM objects, or an empty list if no sites match. Returns ``None``
        when ``nif`` is supplied but no matching client exists.
    """
    stmt = select(Site)
    if not include_archived:
        stmt = stmt.where(Site.archived_at.is_(None))

    if nif is not None:
        client = session.get(Client, nif)
        if not record_is_visible(client, include_archived):
            return None
        stmt = stmt.where(Site.nif == nif)

    stmt = stmt.order_by(Site.city, Site.nif, Site.id).limit(limit).offset(offset)

    return list(session.execute(stmt).scalars().all())


def get_site_by_id(
    site_id: int, session: Session, *, include_archived: bool = False
) -> Site | None:
    """Return one site by primary key, or None when it does not exist."""
    site = session.get(Site, site_id)
    return site if record_is_visible(site, include_archived) else None


def get_site_history_legacy(site_id: int) -> SiteHistory | None:
    """Retrieve the certification history for a site.

    Builds the database connection and reflected table objects needed to query
    certification records for the given site, joins related regulation,
    certifier, finding, and rule data, and converts the result into a ``Site``
    value ordered by inspection date.

    Args:
        site_id: Unique identifier of the site whose certification history
            should be retrieved.

    Returns:
        A formatted site history containing certification and related
        compliance details, or ``None`` if no matching records exist.
    """

    # create engine and metadata
    engine, meta = get_engine_metadata()

    # reflect existing tables
    tables_dict = get_tables(engine, meta)
    certifications_table = tables_dict["certifications_table"]
    regulations_table = tables_dict["regulations_table"]
    certifiers_table = tables_dict["certifiers_table"]
    findings_table = tables_dict["findings_table"]
    rules_table = tables_dict["rules_table"]

    # perform query
    stmt = (
        select(
            certifications_table.c.site_id,
            certifications_table.c.id.label("cert_id"),
            certifications_table.c.result,
            certifications_table.c.resolution_date,
            certifications_table.c.inspection_date,
            regulations_table.c.title.label("reg_title"),
            regulations_table.c.description.label("reg_description"),
            certifiers_table.c.organization_name.label("certifier_org_name"),
            findings_table.c.id.label("finding_id"),
            findings_table.c.finding,
            rules_table.c.rule_index,
            rules_table.c.title.label("rule_title"),
            rules_table.c.description.label("rule_description"),
        )
        .where(certifications_table.c.site_id == site_id)
        .join_from(certifications_table, regulations_table)
        .join_from(certifications_table, certifiers_table)
        .join_from(certifications_table, findings_table, isouter=True)
        .join_from(findings_table, rules_table, isouter=True)
        .order_by(certifications_table.c.inspection_date)
    )
    with engine.connect() as conn:
        results = conn.execute(stmt).mappings().all()
        if not results:
            return None
        return _format_site_history(results)


def get_site_history(
    site_id: int, session: Session, *, include_archived: bool = False
) -> SiteHistory | None:
    """Retrieve the certification history for a site.

    Queries certification records for the given site using the provided session,
    joins related regulation, certifier, finding, and rule data, and converts
    the result into a site-history value ordered by inspection date.

    Args:
        site_id: Unique identifier of the site whose certification history
            should be retrieved.
        include_archived: When true, include archived site, certification,
            regulation, certifier, finding, and rule records.

    Returns:
        A formatted site history containing certification and related
        compliance details, or ``None`` if no matching records exist.
    """

    # perform query
    site = session.get(Site, site_id)
    if not record_is_visible(site, include_archived):
        return None

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
    if not include_archived:
        stmt = stmt.where(Certification.archived_at.is_(None))
        stmt = stmt.where(Regulation.archived_at.is_(None))
        stmt = stmt.where(Certifier.archived_at.is_(None))
        stmt = stmt.where(Finding.id.is_(None) | Finding.archived_at.is_(None))
        stmt = stmt.where(Rule.id.is_(None) | Rule.archived_at.is_(None))

    results = session.execute(stmt).mappings().all()
    if not results:
        return None
    return _format_site_history(results)


def get_site_attachments(
    site_id: int, session: Session, *, include_archived: bool = False
) -> SiteAttachmentsOut | None:
    """Retrieve attachment records for a site with certification and finding context.

    Args:
        site_id: Unique identifier of the site whose attachments should be
            retrieved.
        session: Database session used to execute the attachment query.
        include_archived: When true, include archived site, certification,
            attachment, regulation, rule, and finding records.

    Returns:
        A formatted attachment collection for the site, or ``None`` if no
        matching attachment records exist.
    """
    site = session.get(Site, site_id)
    if not record_is_visible(site, include_archived):
        return None

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
    if not include_archived:
        stmt = stmt.where(Certification.archived_at.is_(None))
        stmt = stmt.where(Attachment.archived_at.is_(None))
        stmt = stmt.where(Regulation.archived_at.is_(None))
        stmt = stmt.where(Finding.id.is_(None) | Finding.archived_at.is_(None))
        stmt = stmt.where(Rule.id.is_(None) | Rule.archived_at.is_(None))

    results = session.execute(stmt).mappings().all()
    if not results:
        return None
    return _format_site_attachments(results)


def get_site_certifications(
    site_id: int,
    session: Session,
    *,
    limit: int | None,
    offset: int,
    include_archived: bool = False,
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
        include_archived: When true, include archived certifications in the results.

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
    if not include_archived:
        stmt = stmt.where(Certification.archived_at.is_(None))

    return list(session.execute(stmt).scalars().all())


def post_new_site(site: SiteCreate, session: Session) -> Site:
    """Persist a new site record.

    Args:
        site: Site creation data validated by the API layer.
        session: Database session used to add and commit the site.

    Returns:
        The created Site ORM object.

    Raises:
        SiteClientNotFoundError: If the client NIF does not exist.
        SiteConflictError: If another integrity conflict prevents the insert.
    """
    site_dict = site.model_dump()
    new_site = Site(**site_dict)
    try:
        session.add(new_site)
        session.commit()
    except IntegrityError as exc:
        session.rollback()

        constraint_name = get_constraint_name(exc)

        if constraint_name == "sites_nif_fkey":
            raise SiteClientNotFoundError(site.nif) from exc

        raise SiteConflictError() from exc

    return new_site


def format_site_certifications(
    site_id: int, certifications: Sequence[Certification]
) -> SiteCertificationsOut:
    """Build a site-level certification collection response.

    Args:
        site_id: Unique identifier of the site whose certifications were queried.
        certifications: Certification ORM objects returned for the site.

    Returns:
        Site certification response containing the site ID and serialized
        certification records.
    """
    return SiteCertificationsOut.model_validate(
        {"site_id": site_id, "certifications": list(certifications)}
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


if __name__ == "__main__":
    from compliance.db.db_access import get_db

    session = get_db()

    print(f"\nsite 71: {get_site_history(71, next(iter(session)))}")

    session = get_db()
    print(f"\nsite 71: {get_site_attachments(71, next(iter(session)))}")

    print(f"\nsite 71: {get_site_history_legacy(71)}")
