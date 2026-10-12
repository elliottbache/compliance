"""Disposable pgvector database support for explicit integration tests."""

import subprocess
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError

_COMPOSE_FILE = Path(__file__).with_name("docker-compose.pgvector.yaml")
_DATABASE_URL = (
    "postgresql+psycopg2://postgres:postgres@127.0.0.1:55432/compliance_rag_test"
)
_DATABASE_READY_TIMEOUT_SECONDS = 30


@contextmanager
def temporary_pgvector_database() -> Generator[Engine, None, None]:
    """Start a disposable pgvector database and remove it afterward."""
    compose_command = ["docker", "compose", "-f", str(_COMPOSE_FILE)]
    engine = None
    try:
        subprocess.run(  # noqa: S603 - command and Compose file are repository constants
            [*compose_command, "up", "--detach", "--wait"],
            check=True,
        )
        engine = create_engine(_DATABASE_URL)
        _wait_for_host_connection(engine)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        subprocess.run(  # noqa: S603 - command and Compose file are repository constants
            [*compose_command, "down", "--volumes", "--remove-orphans"],
            check=False,
        )


def _wait_for_host_connection(engine: Engine) -> None:
    """Wait until PostgreSQL accepts connections through the published port."""
    deadline = time.monotonic() + _DATABASE_READY_TIMEOUT_SECONDS
    while True:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except OperationalError:
            if time.monotonic() >= deadline:
                raise
            engine.dispose()
            time.sleep(0.25)
