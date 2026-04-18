from os import getenv

from dotenv import load_dotenv
from sqlalchemy import Engine, MetaData, Table, create_engine

load_dotenv()
DB_NAME = getenv("POSTGRES_DB")
USER = getenv("POSTGRES_USER")
PASSWORD = getenv("POSTGRES_PASSWORD")
HOST = getenv("POSTGRES_HOST")
if DB_NAME is None or USER is None or PASSWORD is None or HOST is None:
    raise ValueError(".env value is not being read correctly.")
DB_URL = "postgresql+psycopg2://" + USER + ":" + PASSWORD + "@" + HOST + "/" + DB_NAME


def get_engine_metadata() -> tuple[Engine, MetaData]:
    engine = create_engine(DB_URL)
    meta = MetaData()

    return engine, meta


def get_tables(engine: Engine, meta: MetaData) -> dict[str, Table]:
    """Create dict of Tables reflected from current ones in engine."""
    tables_dict = dict()
    tables_dict["certifiers_table"] = Table("certifiers", meta, autoload_with=engine)
    tables_dict["findings_table"] = Table("findings", meta, autoload_with=engine)
    tables_dict["rules_table"] = Table("rules", meta, autoload_with=engine)
    tables_dict["certifications_table"] = Table(
        "certifications", meta, autoload_with=engine
    )
    tables_dict["sites_table"] = Table("sites", meta, autoload_with=engine)
    tables_dict["attachments_table"] = Table("attachments", meta, autoload_with=engine)
    tables_dict["clients_table"] = Table("clients", meta, autoload_with=engine)
    tables_dict["regulations_table"] = Table("regulations", meta, autoload_with=engine)

    return tables_dict
