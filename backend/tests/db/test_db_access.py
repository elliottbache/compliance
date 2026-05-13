import contextlib
from unittest.mock import MagicMock, call, patch

import pytest
from compliance.db.db_access import (
    _build_db_url,
    get_db,
    get_engine,
    get_engine_metadata,
    get_tables,
)


class TestBuildDbUrl:
    def test_builds_url_from_environment(self, monkeypatch) -> None:
        monkeypatch.setenv("POSTGRES_DB", "test_db")
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
        monkeypatch.setenv("POSTGRES_HOST", "localhost")

        assert (
            _build_db_url()
            == "postgresql+psycopg2://test_user:test_password@localhost/test_db"
        )

    def test_raises_when_required_environment_is_missing(self, monkeypatch) -> None:
        monkeypatch.delenv("POSTGRES_DB", raising=False)
        monkeypatch.delenv("POSTGRES_USER", raising=False)
        monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
        monkeypatch.delenv("POSTGRES_HOST", raising=False)

        with pytest.raises(ValueError, match=r"\.env value"):
            _build_db_url()


class TestGetEngine:
    def test_creates_engine_from_built_url(self) -> None:
        mock_engine = MagicMock()

        with (
            patch(
                "compliance.db.db_access._build_db_url",
                return_value="postgresql+psycopg2://test",
            ) as mock_build_db_url,
            patch(
                "compliance.db.db_access.create_engine",
                return_value=mock_engine,
            ) as mock_create_engine,
        ):
            result = get_engine()

        mock_build_db_url.assert_called_once_with()
        mock_create_engine.assert_called_once_with("postgresql+psycopg2://test")
        assert result == mock_engine


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
