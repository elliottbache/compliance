from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from compliance.db.models import (
    Certification,
    Certifier,
    Finding,
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
                cert_dict["findings"] = [_build_finding(row)]
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
                _build_finding(row)
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


def _build_finding(row: Mapping) -> FindingHistory:
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

    print(f"\nsite 71: {get_site_history_by_id(71, next(iter(session)))}")
