from unittest.mock import MagicMock, call, patch

from compliance.db.db_access import get_engine_metadata, get_tables


class TestGetEngineMetadata:
    def test_returns_engine_and_metadata(self) -> None:
        mock_engine = MagicMock()
        mock_meta = MagicMock()

        with (
            patch(
                "compliance.db.db_access.create_engine",
                return_value=mock_engine,
            ) as mock_create_engine,
            patch(
                "compliance.db.db_access.MetaData",
                return_value=mock_meta,
            ) as mock_metadata,
        ):
            engine, meta = get_engine_metadata()

        mock_create_engine.assert_called_once()
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
