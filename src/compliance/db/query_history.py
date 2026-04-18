from collections.abc import Mapping, Sequence

from sqlalchemy import select

from compliance.db.db_access import get_engine_metadata, get_tables
from compliance.schemas import Certification, Finding, Site


def get_site_history(site_id: int) -> Site | None:
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


def _format_site_history(site_history_rows: Sequence[Mapping]) -> Site:
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
                Certification.model_validate(cert_dict)
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

    return Site(**site_history)


def _find_cert_index(
    cert_id: int, site_history_cert_list: list[Certification]
) -> int | None:
    """Returns the index of the certification with the given cert_id, or None if absent."""
    idx = 0
    while (
        idx < len(site_history_cert_list)
        and site_history_cert_list[idx].cert_id != cert_id
    ):
        idx += 1

    return idx if idx < len(site_history_cert_list) else None


def _build_finding(row: Mapping) -> Finding:
    """Build a Finding from the selected fields in a site history row."""
    keys = ["finding_id", "finding", "rule_index", "rule_title", "rule_description"]

    missing_keys = [key for key in keys if key not in row]
    if missing_keys:
        raise KeyError(
            "Missing finding fields in row: "
            f"{missing_keys}. Row keys: {sorted(row.keys())}"
        )
    finding = {k: row[k] for k in keys}

    return Finding.model_validate(finding)


if __name__ == "__main__":

    print(f"site 1: {get_site_history(1)}")
    print(f"site 71: {get_site_history(71)}")
    print(f"site 72: {get_site_history(72)}")
