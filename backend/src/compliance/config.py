"""Runtime configuration loaded from environment variables and backend .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from compliance._helpers import ROOT_DIR


class Settings(BaseSettings):
    """Application settings for environment and database connection config."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / "backend" / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_env: str = "development"
    database_url: str | None = None

    postgres_db: str | None = None
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_host: str | None = None
    postgres_port: int = 5432

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
