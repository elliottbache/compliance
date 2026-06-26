import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def test_app_registers_expected_router_prefixes(main_module):
    """Verify the FastAPI app includes the public API router prefixes."""
    paths = {getattr(route, "path", "") for route in main_module.app.routes}

    assert any(path.startswith("/sites") for path in paths)
    assert any(path.startswith("/certifications") for path in paths)
    assert any(path.startswith("/attachments") for path in paths)
    assert any(path.startswith("/findings") for path in paths)
    assert any(path.startswith("/clients") for path in paths)
    assert any(path.startswith("/certifiers") for path in paths)
    assert any(path.startswith("/rules") for path in paths)
    assert any(path.startswith("/regulations") for path in paths)


class TestLifespan:
    def test_configures_logging_and_runs_startup_database_checks(
        self, main_module, monkeypatch
    ) -> None:
        mock_configure_logging = MagicMock()
        monkeypatch.setattr(main_module, "configure_logging", mock_configure_logging)
        mock_reachable = MagicMock(return_value=True)
        mock_upgrade = MagicMock(return_value=True)
        latest_calls = []
        model_calls = []

        def fake_verify_latest_migration_script(app_env):
            latest_calls.append(app_env)
            return True

        def fake_verify_db_coherence_with_python_models(app_env):
            model_calls.append(app_env)
            return True

        monkeypatch.setattr(main_module, "verify_db_is_reachable", mock_reachable)
        monkeypatch.setattr(
            main_module,
            "verify_latest_migration_script",
            fake_verify_latest_migration_script,
        )
        monkeypatch.setattr(
            main_module,
            "verify_db_coherence_with_python_models",
            fake_verify_db_coherence_with_python_models,
        )
        monkeypatch.setattr(
            main_module,
            "upgrade_to_head_if_development",
            mock_upgrade,
        )

        async def run_lifespan() -> None:
            async with main_module.lifespan(main_module.app):
                pass

        asyncio.run(run_lifespan())

        mock_configure_logging.assert_called_once_with(level="DEBUG")
        mock_reachable.assert_called_once_with()
        assert latest_calls == []
        mock_upgrade.assert_called_once_with(main_module.settings.app_env)
        assert model_calls == [main_module.settings.app_env]

    def test_deployed_env_checks_migration_head(self, main_module, monkeypatch) -> None:
        monkeypatch.setattr(main_module, "configure_logging", lambda *, level: None)
        monkeypatch.setattr(main_module, "verify_db_is_reachable", lambda: True)
        monkeypatch.setattr(
            main_module, "settings", SimpleNamespace(app_env="production")
        )

        mock_latest_check = MagicMock(return_value=True)
        mock_upgrade = MagicMock(return_value=True)
        mock_model_check = MagicMock(return_value=True)
        monkeypatch.setattr(
            main_module, "verify_latest_migration_script", mock_latest_check
        )
        monkeypatch.setattr(main_module, "upgrade_to_head_if_development", mock_upgrade)
        monkeypatch.setattr(
            main_module,
            "verify_db_coherence_with_python_models",
            mock_model_check,
        )

        async def run_lifespan() -> None:
            async with main_module.lifespan(main_module.app):
                pass

        asyncio.run(run_lifespan())

        mock_latest_check.assert_called_once_with("production")
        mock_upgrade.assert_called_once_with("production")
        mock_model_check.assert_called_once_with("production")

    def test_raises_when_database_is_not_reachable(
        self, main_module, monkeypatch
    ) -> None:
        monkeypatch.setattr(main_module, "configure_logging", lambda *, level: None)
        monkeypatch.setattr(main_module, "verify_db_is_reachable", lambda: False)
        mock_latest_check = MagicMock(return_value=True)
        mock_upgrade = MagicMock(return_value=True)
        mock_model_check = MagicMock(return_value=True)
        monkeypatch.setattr(
            main_module, "verify_latest_migration_script", mock_latest_check
        )
        monkeypatch.setattr(main_module, "upgrade_to_head_if_development", mock_upgrade)
        monkeypatch.setattr(
            main_module,
            "verify_db_coherence_with_python_models",
            mock_model_check,
        )

        async def run_lifespan() -> None:
            async with main_module.lifespan(main_module.app):
                pass

        with pytest.raises(RuntimeError, match="Database out of sync"):
            asyncio.run(run_lifespan())

        mock_latest_check.assert_not_called()
        mock_upgrade.assert_not_called()
        mock_model_check.assert_not_called()

    def test_raises_when_database_is_not_at_migration_head(
        self, main_module, monkeypatch
    ) -> None:
        monkeypatch.setattr(main_module, "configure_logging", lambda *, level: None)
        monkeypatch.setattr(main_module, "verify_db_is_reachable", lambda: True)
        monkeypatch.setattr(
            main_module, "settings", SimpleNamespace(app_env="production")
        )
        monkeypatch.setattr(
            main_module, "verify_latest_migration_script", lambda app_env: False
        )
        mock_upgrade = MagicMock(return_value=True)
        mock_model_check = MagicMock(return_value=True)
        monkeypatch.setattr(
            main_module,
            "upgrade_to_head_if_development",
            mock_upgrade,
        )
        monkeypatch.setattr(
            main_module,
            "verify_db_coherence_with_python_models",
            mock_model_check,
        )

        async def run_lifespan() -> None:
            async with main_module.lifespan(main_module.app):
                pass

        with pytest.raises(RuntimeError, match="Database out of sync"):
            asyncio.run(run_lifespan())

        mock_upgrade.assert_not_called()
        mock_model_check.assert_not_called()

    def test_raises_when_development_upgrade_fails(
        self, main_module, monkeypatch
    ) -> None:
        monkeypatch.setattr(main_module, "configure_logging", lambda *, level: None)
        monkeypatch.setattr(main_module, "verify_db_is_reachable", lambda: True)
        mock_latest_check = MagicMock(return_value=True)
        monkeypatch.setattr(
            main_module, "verify_latest_migration_script", mock_latest_check
        )
        monkeypatch.setattr(
            main_module, "upgrade_to_head_if_development", lambda app_env: False
        )
        mock_model_check = MagicMock(return_value=True)
        monkeypatch.setattr(
            main_module,
            "verify_db_coherence_with_python_models",
            mock_model_check,
        )

        async def run_lifespan() -> None:
            async with main_module.lifespan(main_module.app):
                pass

        with pytest.raises(RuntimeError, match="Database out of sync"):
            asyncio.run(run_lifespan())

        mock_latest_check.assert_not_called()
        mock_model_check.assert_not_called()

    def test_raises_when_models_do_not_match_migrations(
        self, main_module, monkeypatch
    ) -> None:
        monkeypatch.setattr(main_module, "configure_logging", lambda *, level: None)
        monkeypatch.setattr(main_module, "verify_db_is_reachable", lambda: True)
        monkeypatch.setattr(
            main_module, "upgrade_to_head_if_development", lambda app_env: True
        )
        monkeypatch.setattr(
            main_module, "verify_latest_migration_script", lambda app_env: True
        )
        monkeypatch.setattr(
            main_module,
            "verify_db_coherence_with_python_models",
            lambda app_env: False,
        )

        async def run_lifespan() -> None:
            async with main_module.lifespan(main_module.app):
                pass

        with pytest.raises(RuntimeError, match="Database out of sync"):
            asyncio.run(run_lifespan())
