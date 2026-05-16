from datetime import UTC, datetime

import pytest
from compliance.db.models import Base
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, object_session

_SQLITE_UTC_DATETIME_FIELDS = ("archived_at", "uploaded_at")


def _normalize_sqlite_datetimes(instance) -> None:
    for field in _SQLITE_UTC_DATETIME_FIELDS:
        value = getattr(instance, field, None)
        if isinstance(value, datetime) and value.tzinfo is None:
            setattr(instance, field, value.replace(tzinfo=UTC))


@event.listens_for(Base, "refresh", propagate=True)
def _normalize_refreshed_sqlite_datetimes(target, context, attrs) -> None:
    session = object_session(target)
    if session is None or session.get_bind().dialect.name != "sqlite":
        return

    _normalize_sqlite_datetimes(target)


@pytest.fixture
def sqlite_session(tmp_path):
    """Create a temporary SQLite DB session for service-level tests."""
    """db_path = tmp_path / "test_compliance.db"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}")"""
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    with Session(engine) as session:

        @event.listens_for(session, "loaded_as_persistent")
        def _normalize_loaded_sqlite_datetimes(session, instance) -> None:
            if session.get_bind().dialect.name == "sqlite":
                _normalize_sqlite_datetimes(instance)

        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()
