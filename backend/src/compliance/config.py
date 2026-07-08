"""Runtime configuration loaded from environment variables and backend .env."""

import os
from pathlib import Path
from typing import Any, Literal

from dotenv import dotenv_values
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from compliance._helpers import ROOT_DIR

AppEnv = Literal["development", "staging", "production"]
AIMode = Literal["mock", "anthropic"]


class Settings(BaseSettings):
    """Application settings for runtime, database, storage, CORS, AI, and scanning."""

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
    attachments_dir: Path = (
        Path.home() / ".local" / "share" / "compliance" / "attachments"
    )
    cors_origin: str | None = None
    ai_mode: AIMode = "mock"
    malware_scanning_enabled: bool = False
    malware_scanner_host: str = "clamav"
    malware_scanner_port: int = 3310

    @model_validator(mode="before")
    @classmethod
    def load_dynamic_env_file(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Dynamically load values from a specific .env file based on app_env."""
        if not isinstance(data, dict):
            data = dict(data)

        app_env = (
            data.get("app_env")
            or data.get("APP_ENV")
            or os.getenv("APP_ENV", "development")
        )

        if app_env in ["staging", "production"]:
            env_file = Path("/etc/compliance/.env")
        else:
            env_file = ROOT_DIR / "backend" / ".env"

        if env_file.is_file():
            # dotenv_values parses the file into a dictionary without modifying os.environ
            file_values = {
                key.lower(): value for key, value in dotenv_values(env_file).items()
            }

            data = {**file_values, **data}

        return data

    @field_validator("attachments_dir")
    @classmethod
    def _expand_attachments_dir(cls, value: Path) -> Path:
        """Expand user-relative attachment paths from env files."""
        return value.expanduser()

    @model_validator(mode="after")
    def _validate_envs(self) -> "Settings":
        """Reject unsafe staging and production configuration values."""
        if self.app_env in ["staging", "production"]:
            if self.postgres_password in ["postgres", ""]:
                raise ValueError(
                    "For production and staging environments, PostgreSQL password must not be postgres.  Set this in .env file.  Check /etc/compliance/.env."
                )
            if self.ai_mode == "mock":
                raise ValueError(
                    "For production and staging environments, AI mode must not be mock.  Set this in .env file.  Check /etc/compliance/.env."
                )
            attach_dir = self.attachments_dir.expanduser().resolve()
            if (
                attach_dir == Path.cwd().resolve()
                or attach_dir
                == Path.home() / ".local" / "share" / "compliance" / "attachments"
            ):
                raise ValueError(
                    "For production and staging environments, attachments directory must not be current directory nor be in the current user's .local folder.  Set this in .env file.  Check /etc/compliance/.env."
                )
            if self.cors_origin in ["http://localhost:5173", "*"]:
                raise ValueError(
                    "For production and staging environments, CORS origin should not be localhost or *.  Set this in .env file.  Check /etc/compliance/.env."
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
