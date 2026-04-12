from collections import defaultdict
from collections.abc import Mapping
from os import getenv
from datetime import date
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validate_call, TypeAdapter
from sqlalchemy import create_engine
from sqlalchemy import MetaData, Table, Column, Integer, String, UniqueConstraint, ForeignKey, Date, CheckConstraint, ForeignKeyConstraint
from sqlalchemy import select, insert
from typing import Sequence

from schemas import Site, Certification

load_dotenv()
DB_NAME = getenv("POSTGRES_DB")
USER = getenv("POSTGRES_USER")
PASSWORD = getenv("POSTGRES_PASSWORD")
HOST = getenv("POSTGRES_HOST")
DB_URL = "postgresql+psycopg2://" + USER + ":" + PASSWORD + "@" + HOST + "/" + DB_NAME

engine = create_engine(DB_URL)
meta = MetaData()

# reflect tables
certifiers_table = Table("certifiers", meta, autoload_with=engine)
findings_table = Table("findings", meta, autoload_with=engine)
rules_table = Table("rules", meta, autoload_with=engine)
certifications_table = Table("certifications", meta, autoload_with=engine)
sites_table = Table("sites", meta, autoload_with=engine)
attachments_table = Table("attachments", meta, autoload_with=engine)
clients_table = Table("clients", meta, autoload_with=engine)
regulations_table = Table("regulations", meta, autoload_with=engine)





def get_site_history(site_id: int) -> Site | None:
    """Retrieve the certification history for a site.

    Queries certification records for the given site and joins related
    regulation, certifier, finding, and rule data. Results are ordered by
    inspection date and converted into a ``Site`` value. If no records are
    found, an empty ``Site`` is returned.

    Args:
        site_id: Unique identifier of the site whose certification history
            should be retrieved.

    Returns:
        Site: A formatted site history containing certification and related
        compliance details, or None if no matching records exist.
    """
    stmt = (
        select(
            certifications_table.c.site_id,
            certifications_table.c.id.label("cert_id"), certifications_table.c[
                "result", "resolution_date", "inspection_date"
            ],
            regulations_table.c.title.label("reg_title"),
            regulations_table.c.description.label("reg_description"),
            certifiers_table.c.organization_name.label("certifier_org_name"),
            findings_table.c.id.label("finding_id"), findings_table.c.finding,
            rules_table.c.rule_index, rules_table.c.title.label("rule_title"),
            rules_table.c.description.label("rule_description")
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
        IndexError: If a row refers to a certification that cannot be found in
            the aggregated certification list.
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
                cert_dict["findings"] = [_create_findings_dict(row)]
            else:
                cert_dict["findings"] = []

            site_history["certifications"].append(cert_dict)

        # add new dict to findings list
        else:
            if row["finding_id"] is None:
                continue

            # find matching list item in certifications for cert_id
            cert_idx = _find_cert_index(row["cert_id"], site_history["certifications"])
            if cert_idx == None:
                raise KeyError(f"Certification list item does not exist: cert_id = "
                    f"{row['cert_id']} in {site_history['certifications']}")

            site_history["certifications"][cert_idx]["findings"].append(
                _create_findings_dict(row)
            )

    site_history["inpsection_count"] = len(site_history["certifications"])
    if site_history["inpsection_count"] > 0:
        site_history["latest_inspection_date"] = \
            site_history["certifications"][-1]["inspection_date"]

    return Site(**site_history)


def _find_cert_index(
        cert_id, site_history_cert_list: list[Certification]
) -> int | None:
    idx = 0
    while (
            idx < len(site_history_cert_list) and
            site_history_cert_list[idx]["cert_id"] != cert_id
    ):
        idx += 1

    return idx if idx < len(site_history_cert_list) else None

def _create_findings_dict(row: Mapping) -> dict:
    """Builds a dictionary containing the selected finding fields from a row."""
    keys = ["finding_id", "finding", "rule_index", "rule_title", "rule_description"]
    return {k: row[k] for k in keys}




if __name__ == "__main__":

    print(f"site 1: {get_site_history(1)}")
    print(f"site 71: {get_site_history(71)}")
    print(f"site 72: {get_site_history(72)}")