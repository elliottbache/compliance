import pytest
from compliance.db.models import Base
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session


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
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()
