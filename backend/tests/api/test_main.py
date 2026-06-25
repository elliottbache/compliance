import asyncio
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
    def test_configures_logging_and_runs_migration_checks(
        self, main_module, monkeypatch
    ) -> None:
        mock_configure_logging = MagicMock()
        monkeypatch.setattr(main_module, "configure_logging", mock_configure_logging)
        latest_calls = []
        model_calls = []

        def fake_verify_latest_migration_script(app_env):
            latest_calls.append(app_env)
            return True

        def fake_verify_db_coherence_with_python_models(app_env):
            model_calls.append(app_env)
            return True

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

        async def run_lifespan() -> None:
            async with main_module.lifespan(main_module.app):
                pass

        asyncio.run(run_lifespan())

        mock_configure_logging.assert_called_once_with(level="DEBUG")
        assert latest_calls == [main_module.settings.app_env]
        assert model_calls == [main_module.settings.app_env]

    def test_raises_when_database_is_not_at_migration_head(
        self, main_module, monkeypatch
    ) -> None:
        monkeypatch.setattr(main_module, "configure_logging", lambda *, level: None)
        monkeypatch.setattr(
            main_module, "verify_latest_migration_script", lambda app_env: False
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

        mock_model_check.assert_not_called()

    def test_raises_when_models_do_not_match_migrations(
        self, main_module, monkeypatch
    ) -> None:
        monkeypatch.setattr(main_module, "configure_logging", lambda *, level: None)
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
