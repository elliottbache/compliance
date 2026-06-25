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


class TestSettingsEnvironmentValidation:
    def test_allows_safe_production_settings(self, tmp_path) -> None:
        settings = Settings(
            app_env="production",
            database_url="postgresql+psycopg2://user:secret@db/app",
            postgres_password="not-postgres",  # noqa: S106
            attachments_dir=tmp_path,
            cors_origins="https://compliance.example.com",
            ai_mode="anthropic",
            _env_file=None,
        )

        assert settings.app_env == "production"
        assert settings.attachments_dir == tmp_path

    @pytest.mark.parametrize("app_env", ["staging", "production"])
    def test_rejects_default_postgres_password_in_deployed_envs(
        self, app_env, tmp_path
    ) -> None:
        with pytest.raises(ValueError, match="PostgreSQL password"):
            Settings(
                app_env=app_env,
                database_url="postgresql+psycopg2://user:postgres@db/app",
                postgres_password="postgres",  # noqa: S106
                attachments_dir=tmp_path,
                cors_origins="https://compliance.example.com",
                ai_mode="anthropic",
                _env_file=None,
            )

    @pytest.mark.parametrize("attachments_dir", [".", ""])
    def test_rejects_current_directory_attachment_storage_in_deployed_envs(
        self, attachments_dir
    ) -> None:
        with pytest.raises(ValueError, match="attachments directory"):
            Settings(
                app_env="production",
                database_url="postgresql+psycopg2://user:secret@db/app",
                postgres_password="not-postgres",  # noqa: S106
                attachments_dir=attachments_dir,
                cors_origins="https://compliance.example.com",
                ai_mode="anthropic",
                _env_file=None,
            )

    def test_rejects_mock_ai_mode_in_deployed_envs(self, tmp_path) -> None:
        with pytest.raises(ValueError, match="AI mode"):
            Settings(
                app_env="staging",
                database_url="postgresql+psycopg2://user:secret@db/app",
                postgres_password="not-postgres",  # noqa: S106
                attachments_dir=tmp_path,
                cors_origins="https://staging.compliance.example.com",
                ai_mode="mock",
                _env_file=None,
            )

    @pytest.mark.parametrize("cors_origins", ["http://localhost:5173", "*"])
    def test_rejects_local_or_wildcard_cors_in_deployed_envs(
        self, cors_origins, tmp_path
    ) -> None:
        with pytest.raises(ValueError, match="CORS origins"):
            Settings(
                app_env="production",
                database_url="postgresql+psycopg2://user:secret@db/app",
                postgres_password="not-postgres",  # noqa: S106
                attachments_dir=tmp_path,
                cors_origins=cors_origins,
                ai_mode="anthropic",
                _env_file=None,
            )
