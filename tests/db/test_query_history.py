from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from compliance.db.query_history import (
    _build_finding,
    _find_cert_index,
    _format_site_history,
    get_site_history,
)
from compliance.schemas import Certification, Finding, Site


@pytest.fixture
def certification_factory():
    def _build(
        cert_id: int,
        *,
        result: str | None = "pass",
        resolution_date=None,
        reg_title: str = "USDA Organic",
        reg_description: str = "Organic certification",
        certifier_org_name: str = "Certifier",
        inspection_date: date | None = date(2024, 1, 10),
        findings=None,
    ) -> Certification:
        return Certification(
            cert_id=cert_id,
            result=result,
            resolution_date=resolution_date,
            reg_title=reg_title,
            reg_description=reg_description,
            certifier_org_name=certifier_org_name,
            inspection_date=inspection_date,
            findings=[] if findings is None else findings,
        )

    return _build


@pytest.fixture
def site_history_row_factory():
    def _build(**overrides):
        row = {
            "site_id": 71,
            "cert_id": 100,
            "result": "pass",
            "resolution_date": None,
            "reg_title": "USDA Organic",
            "reg_description": "Organic certification",
            "certifier_org_name": "Org A",
            "inspection_date": None,
            "finding_id": 1,
            "finding": "Issue A",
            "rule_index": "7 CFR 205.201",
            "rule_title": "Rule A",
            "rule_description": "Rule description A",
        }
        row.update(overrides)
        return row

    return _build


@pytest.fixture
def db_access_mocks():
    mock_engine = MagicMock()
    mock_meta = MagicMock()
    mock_conn = MagicMock()

    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = mock_conn
    mock_context_manager.__exit__.return_value = None
    mock_engine.connect.return_value = mock_context_manager

    mock_tables = {
        "certifications_table": MagicMock(),
        "regulations_table": MagicMock(),
        "certifiers_table": MagicMock(),
        "findings_table": MagicMock(),
        "rules_table": MagicMock(),
    }

    mock_stmt = MagicMock()
    mock_stmt.where.return_value = mock_stmt
    mock_stmt.join_from.return_value = mock_stmt
    mock_stmt.order_by.return_value = mock_stmt

    return {
        "engine": mock_engine,
        "meta": mock_meta,
        "conn": mock_conn,
        "tables": mock_tables,
        "stmt": mock_stmt,
    }


class TestGetSiteHistory:
    def test_returns_none_when_query_returns_no_rows(self, db_access_mocks) -> None:
        db_access_mocks[
            "conn"
        ].execute.return_value.mappings.return_value.all.return_value = []

        with (
            patch(
                "compliance.db.query_history.get_engine_metadata",
                return_value=(db_access_mocks["engine"], db_access_mocks["meta"]),
            ) as mock_get_engine_metadata,
            patch(
                "compliance.db.query_history.get_tables",
                return_value=db_access_mocks["tables"],
            ) as mock_get_tables,
            patch(
                "compliance.db.query_history.select",
                return_value=db_access_mocks["stmt"],
            ) as mock_select,
            patch("compliance.db.query_history._format_site_history") as mock_format,
        ):
            result = get_site_history(71)

        assert result is None
        mock_get_engine_metadata.assert_called_once_with()
        mock_get_tables.assert_called_once_with(
            db_access_mocks["engine"], db_access_mocks["meta"]
        )
        mock_select.assert_called_once()
        mock_format.assert_not_called()

    def test_formats_site_history_when_query_returns_one_row(
        self, site_history_row_factory, db_access_mocks
    ) -> None:
        rows = [
            site_history_row_factory(
                finding_id=None,
                finding=None,
                rule_index=None,
                rule_title=None,
                rule_description=None,
            )
        ]
        formatted_site = Site(
            site_id=71,
            certifications=[],
            inspection_count=1,
            latest_inspection_date=None,
        )
        db_access_mocks[
            "conn"
        ].execute.return_value.mappings.return_value.all.return_value = rows

        with (
            patch(
                "compliance.db.query_history.get_engine_metadata",
                return_value=(db_access_mocks["engine"], db_access_mocks["meta"]),
            ) as mock_get_engine_metadata,
            patch(
                "compliance.db.query_history.get_tables",
                return_value=db_access_mocks["tables"],
            ) as mock_get_tables,
            patch(
                "compliance.db.query_history.select",
                return_value=db_access_mocks["stmt"],
            ) as mock_select,
            patch(
                "compliance.db.query_history._format_site_history",
                return_value=formatted_site,
            ) as mock_format,
        ):
            result = get_site_history(71)

        assert result == formatted_site
        mock_get_engine_metadata.assert_called_once_with()
        mock_get_tables.assert_called_once_with(
            db_access_mocks["engine"], db_access_mocks["meta"]
        )
        mock_select.assert_called_once()
        mock_format.assert_called_once_with(rows)

    def test_formats_site_history_when_query_returns_multiple_rows(
        self, site_history_row_factory, db_access_mocks
    ) -> None:
        rows = [
            site_history_row_factory(
                cert_id=100,
                finding_id=1,
                finding="Issue A",
                rule_index="7 CFR 205.201",
                rule_title="Rule A",
                rule_description="Rule description A",
            ),
            site_history_row_factory(
                cert_id=100,
                finding_id=2,
                finding="Issue B",
                rule_index="7 CFR 205.202",
                rule_title="Rule B",
                rule_description="Rule description B",
            ),
        ]
        formatted_site = Site(
            site_id=71,
            certifications=[],
            inspection_count=1,
            latest_inspection_date=None,
        )
        db_access_mocks[
            "conn"
        ].execute.return_value.mappings.return_value.all.return_value = rows

        with (
            patch(
                "compliance.db.query_history.get_engine_metadata",
                return_value=(db_access_mocks["engine"], db_access_mocks["meta"]),
            ) as mock_get_engine_metadata,
            patch(
                "compliance.db.query_history.get_tables",
                return_value=db_access_mocks["tables"],
            ) as mock_get_tables,
            patch(
                "compliance.db.query_history.select",
                return_value=db_access_mocks["stmt"],
            ) as mock_select,
            patch(
                "compliance.db.query_history._format_site_history",
                return_value=formatted_site,
            ) as mock_format,
        ):
            result = get_site_history(71)

        assert result == formatted_site
        mock_get_engine_metadata.assert_called_once_with()
        mock_get_tables.assert_called_once_with(
            db_access_mocks["engine"], db_access_mocks["meta"]
        )
        mock_select.assert_called_once()
        mock_format.assert_called_once_with(rows)


class TestFormatSiteHistory:
    def test_raises_stop_iteration_when_rows_are_empty(self) -> None:
        with pytest.raises(StopIteration):
            _format_site_history([])

    def test_accepts_list_of_dict_rows(self, site_history_row_factory) -> None:
        rows = [
            site_history_row_factory(
                finding_id=None,
                finding=None,
                rule_index=None,
                rule_title=None,
                rule_description=None,
            )
        ]

        result = _format_site_history(rows)

        assert result.site_id == 71
        assert len(result.certifications) == 1
        assert result.certifications[0].cert_id == 100
        assert result.certifications[0].findings == []

    def test_raises_key_error_when_site_id_is_missing(
        self, site_history_row_factory
    ) -> None:
        row = site_history_row_factory()
        del row["site_id"]

        with pytest.raises(KeyError, match="site_id"):
            _format_site_history([row])

    def test_raises_key_error_when_cert_id_is_missing(
        self, site_history_row_factory
    ) -> None:
        row = site_history_row_factory()
        del row["cert_id"]

        with pytest.raises(KeyError, match="cert_id"):
            _format_site_history([row])

    def test_creates_empty_findings_when_finding_id_is_none(
        self, site_history_row_factory
    ) -> None:
        rows = [
            site_history_row_factory(
                finding_id=None,
                finding=None,
                rule_index=None,
                rule_title=None,
                rule_description=None,
            )
        ]

        result = _format_site_history(rows)

        assert len(result.certifications) == 1
        assert result.certifications[0].findings == []

    def test_appends_findings_when_certification_already_exists(
        self, site_history_row_factory
    ) -> None:
        rows = [
            site_history_row_factory(
                cert_id=100,
                finding_id=1,
                finding="Issue A",
                rule_index="7 CFR 205.201",
                rule_title="Rule A",
                rule_description="Rule description A",
            ),
            site_history_row_factory(
                cert_id=100,
                finding_id=2,
                finding="Issue B",
                rule_index="7 CFR 205.202",
                rule_title="Rule B",
                rule_description="Rule description B",
            ),
        ]

        result = _format_site_history(rows)

        assert len(result.certifications) == 1
        assert result.certifications[0].cert_id == 100
        assert len(result.certifications[0].findings) == 2
        assert result.certifications[0].findings[0].finding_id == 1
        assert result.certifications[0].findings[1].finding_id == 2

    def test_creates_multiple_certifications_and_sets_inspection_count(
        self, site_history_row_factory
    ) -> None:
        rows = [
            site_history_row_factory(
                cert_id=100,
                inspection_date=date(2024, 1, 10),
                finding_id=1,
                finding="Issue A",
                rule_index="7 CFR 205.201",
                rule_title="Rule A",
                rule_description="Rule description A",
            ),
            site_history_row_factory(
                cert_id=200,
                inspection_date=date(2024, 2, 1),
                certifier_org_name="Org B",
                finding_id=99,
                finding="Issue B",
                rule_index="7 CFR 205.202",
                rule_title="Rule B",
                rule_description="Rule description B",
            ),
        ]

        result = _format_site_history(rows)

        assert len(result.certifications) == 2
        assert result.certifications[0].cert_id == 100
        assert result.certifications[1].cert_id == 200
        assert result.inspection_count == 2
        assert result.latest_inspection_date == date(2024, 2, 1)

    def test_sets_latest_inspection_date_to_none_when_inspection_count_is_positive(
        self, site_history_row_factory
    ) -> None:
        rows = [
            site_history_row_factory(
                inspection_date=None,
                finding_id=None,
                finding=None,
                rule_index=None,
                rule_title=None,
                rule_description=None,
            )
        ]

        result = _format_site_history(rows)

        assert result.inspection_count == 1
        assert result.latest_inspection_date is None


class TestFindCertIndex:
    def test_returns_index_when_cert_is_first_in_list(
        self, certification_factory
    ) -> None:
        certs = [certification_factory(100), certification_factory(200)]

        assert _find_cert_index(100, certs) == 0

    def test_returns_index_when_cert_is_last_in_list(
        self, certification_factory
    ) -> None:
        certs = [certification_factory(100), certification_factory(200)]

        assert _find_cert_index(200, certs) == 1

    def test_returns_none_when_cert_is_not_in_list(self, certification_factory) -> None:
        certs = [certification_factory(100), certification_factory(200)]

        assert _find_cert_index(999, certs) is None

    def test_returns_none_when_list_is_empty(self) -> None:
        assert _find_cert_index(100, []) is None


class TestBuildFinding:
    def test_returns_finding_for_valid_row(self, site_history_row_factory) -> None:
        row = site_history_row_factory()

        result = _build_finding(row)

        assert isinstance(result, Finding)
        assert result.finding_id == 1
        assert result.finding == "Issue A"
        assert result.rule_index == "7 CFR 205.201"
        assert result.rule_title == "Rule A"
        assert result.rule_description == "Rule description A"

    def test_raises_key_error_when_required_key_is_missing(
        self, site_history_row_factory
    ) -> None:
        row = site_history_row_factory()
        del row["rule_description"]

        with pytest.raises(KeyError, match="Missing finding fields"):
            _build_finding(row)

    def test_ignores_extra_keys(self, site_history_row_factory) -> None:
        row = site_history_row_factory(unused_field="ignored")

        result = _build_finding(row)

        assert result.finding_id == 1
        assert not hasattr(result, "unused_field")

    def test_allows_none_rule_title(self, site_history_row_factory) -> None:
        row = site_history_row_factory(rule_title=None)

        result = _build_finding(row)

        assert result.rule_title is None
