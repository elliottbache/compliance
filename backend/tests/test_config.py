import pytest
from compliance.config import Settings
from sqlalchemy import URL


class TestSettingsDatabaseUrl:
    def test_uses_database_url_when_set(self) -> None:
        settings = Settings(
            database_url="postgresql+psycopg2://direct-user:direct-pass@db/app",
            postgres_db="ignored_db",
            postgres_user="ignored_user",
            postgres_password="ignored_password",  # noqa: S106
            postgres_host="ignored_host",
            _env_file=None,
        )

        assert (
            settings.resolved_database_url
            == "postgresql+psycopg2://direct-user:direct-pass@db/app"
        )
        assert (
            settings.resolved_database_url_str
            == "postgresql+psycopg2://direct-user:direct-pass@db/app"
        )

    def test_builds_url_from_postgres_parts(self) -> None:
        settings = Settings(
            database_url=None,
            postgres_db="compliance_db",
            postgres_user="postgres",
            postgres_password="p@ ss/word",  # noqa: S106
            postgres_host="localhost",
            postgres_port=5433,
            _env_file=None,
        )

        url = settings.resolved_database_url

        assert isinstance(url, URL)
        assert url.drivername == "postgresql+psycopg2"
        assert url.username == "postgres"
        assert url.password == "p@ ss/word"  # noqa: S105
        assert url.host == "localhost"
        assert url.port == 5433
        assert url.database == "compliance_db"
        assert "p%40 ss%2Fword" in settings.resolved_database_url_str

    def test_raises_when_database_config_is_incomplete(self) -> None:
        settings = Settings(
            database_url=None,
            postgres_db="compliance_db",
            postgres_user="postgres",
            postgres_password=None,
            postgres_host="localhost",
            _env_file=None,
        )

        with pytest.raises(ValueError, match="DATABASE_URL or complete POSTGRES_"):
            _ = settings.resolved_database_url
