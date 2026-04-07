from os import getenv
from datetime import date
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validate_call
from sqlalchemy import create_engine
from sqlalchemy import MetaData, Table, Column, Integer, String, UniqueConstraint, ForeignKey, Date, CheckConstraint, ForeignKeyConstraint
from sqlalchemy import select, insert

load_dotenv()
DB_NAME = getenv("POSTGRES_DB")
USER = getenv("POSTGRES_USER")
PASSWORD = getenv("POSTGRES_PASSWORD")
HOST = getenv("POSTGRES_HOST")
DB_URL = "postgresql+psycopg2://" + USER + ":" + PASSWORD + "@" + HOST + "/" + DB_NAME


class FindingRule(BaseModel):
    id: int
    finding: str
    rule_id: int
    rule_index: str
    rule_title: str | None

class Certification(BaseModel):
    id: int
    certifier_id: int
    regulation_id: int
    site_id: int
    result: str | None
    inspection_date: date | None
    resolution_date: date | None



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


def format_site_history():
    pass


def get_site_history(site_id: int):
    """Query specific site's history from db.

    Returns empty list if no history for this site.
    invalid site_id format → error
    site not found → error
    site exists but no history → valid empty result
    dates in one consistent format, ideally ISO
    sorted deterministically, ideally newest first
    no guessed fields, no summaries, no “likely recurrent” language
    """
    # query database
    stmt = (
        select(sites_table)
        .where(sites_table.c.id == site_id)
        #.join(STOPPED HERE!!!)
    )
    # return structured data
    pass


def get_certifications():
    ## DO THIS!!!!!
    pass


def get_findings(finding_id: int) -> list[FindingRule]:
    """Fetches findings and their associated rule metadata for a specific finding ID.

    Queries the findings table, joins the related rule record, and returns the
    result as a list of `FindingRule` objects.

    Args:
        finding_id: The ID of the finding to retrieve.

    Returns:
        A list of `FindingRule` instances matching the given finding ID. The list
        is empty if no matching finding is found.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: If the database query fails.
        ValidationError: If a result row cannot be unpacked into `FindingRule`.
    """
    out_columns = [
        findings_table.c.id,
        findings_table.c.finding,
        findings_table.c.rule_id,
        rules_table.c.rule_index,
        rules_table.c.title.label("rule_title"),
    ]
    stmt = (
        select(*out_columns)
        .select_from(findings_table)
        .where(findings_table.c.id == finding_id)
        .join_from(findings_table, rules_table, findings_table.c.rule_id == rules_table.c.id)
    )
    with engine.connect() as conn:
        results = conn.execute(stmt).mappings().all()
        for row in results:
            print(row)
        return [FindingRule(**row) for row in results]


if __name__ == "__main__":

    print(get_findings(13))