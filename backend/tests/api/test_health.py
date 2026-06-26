from types import SimpleNamespace

import pytest
from compliance.api.routers import health
from compliance.services.schemas import HealthCheckResult
from fastapi import HTTPException


class TestReadinessCheck:
    def test_returns_dependency_statuses(self, monkeypatch) -> None:
        monkeypatch.setattr(health, "verify_db_is_reachable", lambda: True)
        monkeypatch.setattr(
            health, "verify_latest_migration_script", lambda app_env: True
        )
        monkeypatch.setattr(
            health, "verify_db_coherence_with_python_models", lambda app_env: True
        )
        monkeypatch.setattr(health, "check_attachment_storage", lambda: True)
        monkeypatch.setattr(health, "settings", SimpleNamespace(app_env="production"))

        result = health.readiness_check()

        assert result == HealthCheckResult(
            database_reachable=True,
            migration_current=True,
            model_drift_absent=True,
            attachment_storage=True,
        )

    def test_raises_503_when_database_is_unreachable(self, monkeypatch) -> None:
        monkeypatch.setattr(health, "verify_db_is_reachable", lambda: False)

        with pytest.raises(HTTPException) as exc_info:
            health.readiness_check()

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == "Database unreachable."

    def test_raises_503_when_database_is_not_at_migration_head(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(health, "verify_db_is_reachable", lambda: True)
        monkeypatch.setattr(
            health, "verify_latest_migration_script", lambda app_env: False
        )
        monkeypatch.setattr(
            health, "verify_db_coherence_with_python_models", lambda app_env: True
        )
        monkeypatch.setattr(health, "settings", SimpleNamespace(app_env="production"))

        with pytest.raises(HTTPException) as exc_info:
            health.readiness_check()

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == "Database not up to date."

    def test_raises_503_when_models_do_not_match_migrations(self, monkeypatch) -> None:
        monkeypatch.setattr(health, "verify_db_is_reachable", lambda: True)
        monkeypatch.setattr(
            health, "verify_latest_migration_script", lambda app_env: True
        )
        monkeypatch.setattr(
            health, "verify_db_coherence_with_python_models", lambda app_env: False
        )
        monkeypatch.setattr(health, "settings", SimpleNamespace(app_env="production"))

        with pytest.raises(HTTPException) as exc_info:
            health.readiness_check()

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == "Database not up to date."

    def test_raises_503_when_attachment_storage_is_unreachable(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(health, "verify_db_is_reachable", lambda: True)
        monkeypatch.setattr(
            health, "verify_latest_migration_script", lambda app_env: True
        )
        monkeypatch.setattr(
            health, "verify_db_coherence_with_python_models", lambda app_env: True
        )
        monkeypatch.setattr(health, "check_attachment_storage", lambda: False)
        monkeypatch.setattr(health, "settings", SimpleNamespace(app_env="production"))

        with pytest.raises(HTTPException) as exc_info:
            health.readiness_check()

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == "Attachment storage unreachable."
