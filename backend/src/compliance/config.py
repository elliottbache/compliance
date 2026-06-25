"""Runtime configuration loaded from environment variables and backend .env."""

from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from compliance._helpers import ROOT_DIR

AppEnv = Literal["development", "staging", "production"]
AIMode = Literal["mock", "anthropic"]


class Settings(BaseSettings):
    """Application settings for runtime, database, storage, CORS, and AI config."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / "backend" / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_env: AppEnv = "development"
    database_url: str | None = None

    postgres_db: str | None = None
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_host: str | None = None
    postgres_port: int = 5432
    attachments_dir: Path = ROOT_DIR / "backend" / "storage" / "attachments"
    cors_origins: str | None = None
    ai_mode: AIMode = "mock"

    @model_validator(mode="after")
    def _validate_envs(self) -> "Settings":
        """Reject unsafe staging and production configuration values."""
        if self.app_env in ["staging", "production"]:
            if self.postgres_password in ["postgres", ""]:
                raise ValueError(
                    "For production and staging environments, PostgreSQL password must not be postgres.  Set this in .env file.  Check /opt/compliance/.env."
                )
            if self.ai_mode == "mock":
                raise ValueError(
                    "For production and staging environments, AI mode must not be mock.  Set this in .env file.  Check /opt/compliance/.env."
                )
            if self.attachments_dir.expanduser().resolve() == Path.cwd().resolve():
                raise ValueError(
                    "For production and staging environments, attachments directory must not be current directory.  Set this in .env file.  Check /opt/compliance/.env."
                )
            if self.cors_origins in ["http://localhost:5173", "*"]:
                raise ValueError(
                    "For production and staging environments, CORS origins should not be localhost or *.  Set this in .env file.  Check /opt/compliance/.env."
                )

        return self

    @property
    def resolved_database_url(self) -> str | URL:
        """Return a SQLAlchemy database URL from DATABASE_URL or POSTGRES_* parts."""
        if self.database_url:
            return self.database_url

        if not all(
            [
                self.postgres_db,
                self.postgres_user,
                self.postgres_password,
                self.postgres_host,
            ]
        ):
            raise ValueError("DATABASE_URL or complete POSTGRES_* are required.")

        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def resolved_database_url_str(self) -> str:
        """Return the resolved database URL as an unmasked string for Alembic."""
        url = self.resolved_database_url

        if isinstance(url, URL):
            return url.render_as_string(hide_password=False)

        return url


settings = Settings()
