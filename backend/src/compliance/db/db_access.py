"""SQLAlchemy engine, session, metadata, and table reflection helpers."""

from collections.abc import Generator
from functools import cache

from sqlalchemy import Engine, MetaData, Table, create_engine
from sqlalchemy.orm import Session

from compliance._helpers import ROOT_DIR
from compliance.config import settings

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)

_DOTENV_PATH = ROOT_DIR / "backend" / ".env"


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped database session for FastAPI dependencies."""
    with Session(get_engine()) as session:
        yield session


@cache
def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine for the configured database."""
    return create_engine(settings.resolved_database_url)


def get_engine_metadata() -> tuple[Engine, MetaData]:
    """Create a SQLAlchemy engine and metadata object for database queries."""
    engine = get_engine()
    meta = MetaData()

    return engine, meta


def get_tables(engine: Engine, meta: MetaData) -> dict[str, Table]:
    """Reflect the core application tables from the configured database engine."""
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
