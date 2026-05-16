from collections.abc import Mapping, Sequence

from compliance.db.models import (
    Certification,
    Certifier,
    Client,
    Finding,
    Regulation,
    Rule,
    Site,
)
from compliance.schemas import CertificationHistory, FindingHistory, SiteHistory
from compliance.services.lifecycle import record_is_visible
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_site_history(
    session: Session, site_id: int, *, include_archived: bool = False
) -> SiteHistory | None:
    """Retrieve the certification history for a site.

    Queries certification records for the given site using the provided session,
    joins related regulation, certifier, finding, and rule data, and converts
    the result into a site-history value ordered by inspection date.

    Args:
        session: Database session used to execute the certification history query.
        site_id: Unique identifier of the site whose certification history
            should be retrieved.
        include_archived: When true, include archived site, certification,
            regulation, certifier, finding, and rule records. By default,
            archived finding and rule rows are omitted from the optional
            history context without hiding otherwise visible certifications.

    Returns:
        A formatted site history containing visible certification and related
        compliance details, or ``None`` if the site is not visible or no
        matching visible certification records exist.
    """

    # perform query
    site = session.get(Site, site_id)
    if site is None or not record_is_visible(site, include_archived):
        return None

    client = session.get(Client, site.nif)
    if not record_is_visible(client, include_archived):
        return None

    finding_join_condition = Finding.certification_id == Certification.id
    rule_join_condition = Rule.id == Finding.rule_id
    if not include_archived:
        finding_join_condition = finding_join_condition & Finding.archived_at.is_(None)
        rule_join_condition = rule_join_condition & Rule.archived_at.is_(None)

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
        .outerjoin(Finding, finding_join_condition)
        .outerjoin(Rule, rule_join_condition)
        .order_by(Certification.inspection_date)
    )
    if not include_archived:
        stmt = stmt.where(Certification.archived_at.is_(None))
        stmt = stmt.where(Regulation.archived_at.is_(None))
        stmt = stmt.where(Certifier.archived_at.is_(None))

    results = session.execute(stmt).mappings().all()
    if not results:
        return None
    return _format_site_history(results)


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
