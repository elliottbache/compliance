from collections.abc import Generator
from functools import cache
from os import getenv

from dotenv import load_dotenv
from sqlalchemy import Engine, MetaData, Table, create_engine
from sqlalchemy.orm import Session

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)


def _build_db_url() -> str:
    """Build the database URL from environment variables.

    Raises:
        ValueError: If any required database environment variable is missing.
    """
    load_dotenv()

    db_name = getenv("POSTGRES_DB")
    user = getenv("POSTGRES_USER")
    password = getenv("POSTGRES_PASSWORD")
    host = getenv("POSTGRES_HOST")

    if db_name is None or user is None or password is None or host is None:
        raise ValueError(".env value is not being read correctly.")

    return f"postgresql+psycopg2://{user}:{password}@{host}/{db_name}"


@cache
def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine for the configured database."""
    return create_engine(_build_db_url())


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped database session for FastAPI dependencies."""
    with Session(get_engine()) as session:
        yield session


def get_engine_metadata() -> tuple[Engine, MetaData]:
    """Create a SQLAlchemy engine and metadata object for database queries."""
    engine = get_engine()
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
