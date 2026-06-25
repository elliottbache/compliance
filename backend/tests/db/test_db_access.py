import contextlib
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import compliance.db.db_access as db_access
from alembic.util.exc import CommandError
from compliance.db.db_access import (
    get_db,
    get_engine,
    get_engine_metadata,
    get_tables,
)


class TestGetEngine:
    def setup_method(self) -> None:
        get_engine.cache_clear()

    def teardown_method(self) -> None:
        get_engine.cache_clear()

    def test_creates_engine_from_resolved_settings_url(self) -> None:
        mock_engine = MagicMock()
        mock_settings = SimpleNamespace(
            resolved_database_url="postgresql+psycopg2://test"
        )

        with (
            patch(
                "compliance.db.db_access.settings",
                mock_settings,
            ),
            patch(
                "compliance.db.db_access.create_engine",
                return_value=mock_engine,
            ) as mock_create_engine,
        ):
            result = get_engine()

        mock_create_engine.assert_called_once_with("postgresql+psycopg2://test")
        assert result == mock_engine

    def test_reuses_engine_after_first_creation(self) -> None:
        mock_engine = MagicMock()
        mock_settings = SimpleNamespace(
            resolved_database_url="postgresql+psycopg2://test"
        )

        with (
            patch(
                "compliance.db.db_access.settings",
                mock_settings,
            ),
            patch(
                "compliance.db.db_access.create_engine",
                return_value=mock_engine,
            ) as mock_create_engine,
        ):
            first_result = get_engine()
            second_result = get_engine()

        mock_create_engine.assert_called_once_with("postgresql+psycopg2://test")
        assert first_result is mock_engine
        assert second_result is mock_engine


class TestGetDb:
    def test_yields_session_created_with_module_engine(self) -> None:
        mock_engine = MagicMock()
        mock_session = MagicMock()
        mock_session_context = MagicMock()
        mock_session_context.__enter__.return_value = mock_session
        mock_session_context.__exit__.return_value = None

        with (
            patch("compliance.db.db_access.get_engine", return_value=mock_engine),
            patch(
                "compliance.db.db_access.Session",
                return_value=mock_session_context,
            ) as mock_session_class,
        ):
            db_generator = get_db()
            result = next(db_generator)

            assert result is mock_session
            mock_session_class.assert_called_once_with(mock_engine)

            with contextlib.suppress(StopIteration):
                next(db_generator)

        mock_session_context.__exit__.assert_called_once()


class TestGetEngineMetadata:
    def test_returns_engine_and_metadata(self) -> None:
        mock_engine = MagicMock()
        mock_meta = MagicMock()

        with (
            patch(
                "compliance.db.db_access.get_engine",
                return_value=mock_engine,
            ) as mock_get_engine,
            patch(
                "compliance.db.db_access.MetaData",
                return_value=mock_meta,
            ) as mock_metadata,
        ):
            engine, meta = get_engine_metadata()

        mock_get_engine.assert_called_once()
        mock_metadata.assert_called_once_with()
        assert engine == mock_engine
        assert meta == mock_meta


class TestGetTables:
    def test_reflects_expected_tables_and_returns_dict(self) -> None:
        mock_engine = MagicMock()
        mock_meta = MagicMock()

        certifiers_table = MagicMock()
        findings_table = MagicMock()
        rules_table = MagicMock()
        certifications_table = MagicMock()
        sites_table = MagicMock()
        attachments_table = MagicMock()
        clients_table = MagicMock()
        regulations_table = MagicMock()

        with patch(
            "compliance.db.db_access.Table",
            side_effect=[
                certifiers_table,
                findings_table,
                rules_table,
                certifications_table,
                sites_table,
                attachments_table,
                clients_table,
                regulations_table,
            ],
        ) as mock_table:
            result = get_tables(mock_engine, mock_meta)

        assert result == {
            "certifiers_table": certifiers_table,
            "findings_table": findings_table,
            "rules_table": rules_table,
            "certifications_table": certifications_table,
            "sites_table": sites_table,
            "attachments_table": attachments_table,
            "clients_table": clients_table,
            "regulations_table": regulations_table,
        }

        assert mock_table.call_args_list == [
            call("certifiers", mock_meta, autoload_with=mock_engine),
            call("findings", mock_meta, autoload_with=mock_engine),
            call("rules", mock_meta, autoload_with=mock_engine),
            call("certifications", mock_meta, autoload_with=mock_engine),
            call("sites", mock_meta, autoload_with=mock_engine),
            call("attachments", mock_meta, autoload_with=mock_engine),
            call("clients", mock_meta, autoload_with=mock_engine),
            call("regulations", mock_meta, autoload_with=mock_engine),
        ]


class TestGetAlembicConfig:
    def test_uses_absolute_runtime_paths_and_disables_logger_config(self) -> None:
        cfg = db_access._get_alembic_config()

        assert cfg.get_main_option("script_location") == str(
            db_access.ROOT_DIR / "backend" / "migrations"
        )
        assert cfg.get_main_option("prepend_sys_path") == str(
            db_access.ROOT_DIR / "backend" / "src"
        )
        assert cfg.attributes["configure_logger"] is False

    def test_can_enable_alembic_logger_config_for_cli_like_use(self) -> None:
        cfg = db_access._get_alembic_config(configure_logger=True)

        assert cfg.attributes["configure_logger"] is True


class TestVerifyLatestMigrationScript:
    def test_returns_true_when_database_is_at_head(self) -> None:
        cfg = MagicMock()

        with (
            patch("compliance.db.db_access._get_alembic_config", return_value=cfg),
            patch("compliance.db.db_access.command.current") as mock_current,
            patch("compliance.db.db_access.command.upgrade") as mock_upgrade,
        ):
            result = db_access.verify_latest_migration_script("production")

        assert result is True
        mock_current.assert_called_once_with(cfg, check_heads=True)
        mock_upgrade.assert_not_called()

    def test_development_upgrades_to_head_when_database_is_behind(self) -> None:
        cfg = MagicMock()

        with (
            patch("compliance.db.db_access._get_alembic_config", return_value=cfg),
            patch(
                "compliance.db.db_access.command.current",
                side_effect=CommandError("behind head"),
            ),
            patch("compliance.db.db_access.command.upgrade") as mock_upgrade,
        ):
            result = db_access.verify_latest_migration_script("development")

        assert result is True
        mock_upgrade.assert_called_once_with(cfg, "head")

    def test_development_returns_false_when_upgrade_fails(self) -> None:
        cfg = MagicMock()

        with (
            patch("compliance.db.db_access._get_alembic_config", return_value=cfg),
            patch(
                "compliance.db.db_access.command.current",
                side_effect=CommandError("behind head"),
            ),
            patch(
                "compliance.db.db_access.command.upgrade",
                side_effect=CommandError("upgrade failed"),
            ),
        ):
            result = db_access.verify_latest_migration_script("development")

        assert result is False

    def test_deployed_env_returns_false_without_auto_upgrade_when_database_is_behind(
        self,
    ) -> None:
        cfg = MagicMock()

        with (
            patch("compliance.db.db_access._get_alembic_config", return_value=cfg),
            patch(
                "compliance.db.db_access.command.current",
                side_effect=CommandError("behind head"),
            ),
            patch("compliance.db.db_access.command.upgrade") as mock_upgrade,
        ):
            result = db_access.verify_latest_migration_script("production")

        assert result is False
        mock_upgrade.assert_not_called()


class TestVerifyDbCoherenceWithPythonModels:
    def test_returns_true_when_models_match_migrations(self) -> None:
        cfg = MagicMock()

        with (
            patch("compliance.db.db_access._get_alembic_config", return_value=cfg),
            patch("compliance.db.db_access.command.check") as mock_check,
        ):
            result = db_access.verify_db_coherence_with_python_models("production")

        assert result is True
        mock_check.assert_called_once_with(cfg)

    def test_returns_false_when_models_differ_from_migrations(self) -> None:
        cfg = MagicMock()

        with (
            patch("compliance.db.db_access._get_alembic_config", return_value=cfg),
            patch(
                "compliance.db.db_access.command.check",
                side_effect=CommandError("new upgrade operations detected"),
            ),
        ):
            result = db_access.verify_db_coherence_with_python_models("development")

        assert result is False
