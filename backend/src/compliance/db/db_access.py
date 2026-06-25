"""SQLAlchemy engine, session, metadata, and table reflection helpers."""

import logging
from collections.abc import Generator
from functools import cache

from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from sqlalchemy import Engine, MetaData, Table, create_engine
from sqlalchemy.orm import Session

from compliance._helpers import ROOT_DIR
from compliance.config import AppEnv, settings

logger = logging.getLogger(__name__)

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


def verify_latest_migration_script(app_env: AppEnv) -> bool:
    """Return whether the database is at the latest Alembic migration.

    In development, an out-of-date database is upgraded to ``head`` because
    local startup favors convenience. In staging and production, this check
    only reports failure so operators can run the backup-first migration flow.
    """

    try:
        cfg = _get_alembic_config()
        command.current(cfg, check_heads=True)
        logger.info("Database schema is coherent with latest Alembic migration script!")

        return True

    except CommandError as exc:
        if app_env == "development":
            logger.warning(
                f"Database out of sync with latest Alembic migration script: {exc}!\nUpgrading to head."
            )
            try:
                command.upgrade(cfg, "head")
                return True

            except CommandError as err:
                logger.critical(
                    f"Database failed upgrading to head: {err}!\nTry running:\nalembic -c backend/alembic.ini upgrade head"
                )

        else:
            logger.critical(
                f"Database out of sync with latest Alembic migration script: {exc}!\nRun:\nalembic -c backend/alembic.ini upgrade head"
            )

    return False


def _get_alembic_config(*, configure_logger: bool = False) -> Config:
    """Build an Alembic config with absolute runtime paths.

    The application may start from outside the repository root, so runtime
    Alembic calls must not rely on cwd-relative ``script_location`` or
    ``prepend_sys_path`` values. ``configure_logger`` defaults to false so
    in-app Alembic checks do not replace the application logging handlers.
    """
    cfg = Config(ROOT_DIR / "backend" / "alembic.ini")
    cfg.set_main_option("script_location", str(ROOT_DIR / "backend" / "migrations"))
    cfg.set_main_option("prepend_sys_path", str(ROOT_DIR / "backend" / "src"))
    cfg.attributes["configure_logger"] = configure_logger

    return cfg


def verify_db_coherence_with_python_models(app_env: AppEnv) -> bool:
    """Return whether Alembic autogenerate sees no ORM/model drift."""

    try:
        cfg = _get_alembic_config()
        command.check(cfg)
        logger.info("Database schema is coherent with SQLAlchemy models!")

        return True

    except CommandError as exc:
        if app_env == "development":
            logger.warning(
                f"Database is at migration head, but SQLAlchemy models differ from migrations: {exc}!\n\nGenerate migration script by running:\nalembic -c backend/alembic.ini revision --autogenerate -m 'describe change'\nReview the generated migration, then run: alembic -c backend/alembic.ini upgrade head"
            )
        else:
            logger.critical(
                f"Database is at migration head, but SQLAlchemy models differ from migrations: {exc}!\n\nGenerate migration script by running:\nalembic -c backend/alembic.ini revision --autogenerate -m 'describe change'\nReview the generated migration, then run: alembic -c backend/alembic.ini upgrade head"
            )

    return False
