from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from compliance.db.models import (
    Certification,
    Client,
    Site,
)
from compliance.schemas import FindingHistory, SiteHistory
from compliance.services.attachments.formatting import (
    _build_finding_history_from_site_attachments,
)
from compliance.services.certifications import (
    get_certifications,
)
from compliance.services.schemas import (
    ArchiveRequest,
    SiteAttachmentsOut,
    SiteCertificationsOut,
    SiteCreate,
)
from compliance.services.sites import (
    SiteClientNotFoundError,
    SiteConflictError,
    SiteNotFoundError,
    _build_finding_history_from_site_history,
    _format_site_attachments,
    _format_site_history,
    format_site_certifications,
    get_site_attachments,
    get_site_by_id,
    get_site_certifications,
    get_site_history,
    get_sites,
    post_new_site,
    post_site_archived_by_id,
    post_site_restored_by_id,
)
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def site_history_row_factory():
    def _build(**overrides):
        row = {
            "site_id": 71,
            "cert_id": 100,
            "result": "Pass",
            "resolution_date": None,
            "reg_title": "USDA Organic",
            "reg_description": "Organic certification",
            "certifier_org_name": "Org A",
            "inspection_date": date(2026, 4, 1),
            "finding_id": 1,
            "finding": "Missing document",
            "rule_index": "7 CFR 205.201",
            "rule_title": "Organic plan",
            "rule_description": "Producer must maintain an organic system plan.",
            "archived_at": None,
            "archive_reason": None,
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


@pytest.fixture
def attachment_out_factory():
    def _build(**overrides):
        row = {
            "Attachment": SimpleNamespace(
                id=50,
                file_name="evidence",
                file_path="dummy/evidence.pdf",
                description="Inspection evidence",
                uploaded_at=datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
                archived_at=None,
                archive_reason=None,
                certification_id=100,
            ),
            "Certification": SimpleNamespace(
                site_id=71,
                id=100,
                regulation_id=5,
                inspection_date=date(2026, 4, 1),
            ),
            "Regulation": SimpleNamespace(
                id=5,
                title="USDA Organic",
            ),
            "Finding": SimpleNamespace(
                id=1,
                finding="Missing document",
            ),
            "FindingAttachment": MagicMock(),
            "Rule": SimpleNamespace(
                id=10,
                rule_index="7 CFR 205.201",
                title="Organic plan",
                description="Producer must maintain an organic system plan.",
            ),
        }
        row.update(overrides)
        return row

    return _build


def _site_create(**overrides) -> SiteCreate:
    data = {
        "nif": "A1234567B",
        "city": "Madrid",
        "postal_code": 28013,
        "street": "Gran Via",
        "street_number": None,
        "suite": None,
        "address_info": "Main entrance",
    }
    data.update(overrides)
    return SiteCreate(**data)


class TestGetSites:
    def test_returns_sites_from_session(self, site_row_factory) -> None:
        session = MagicMock()
        sites = [
            site_row_factory(),
            site_row_factory(id=13, city="Valencia"),
        ]
        session.execute.return_value.scalars.return_value.all.return_value = sites

        result = get_sites(session, nif=None, limit=10, offset=5)

        assert result == sites

    def test_orders_sites_by_city_nif_then_id(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_sites(session, nif=None, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert "ORDER BY sites.city, sites.nif, sites.id" in str(stmt)

    def test_excludes_archived_sites_by_default(
        self, sqlite_session, db_factory, site_row_factory
    ) -> None:
        db_factory()
        archived = site_row_factory(
            id=13,
            city="Valencia",
            archived_at=datetime.now(UTC),
            archive_reason="closed",
        )
        sqlite_session.add(archived)
        sqlite_session.commit()

        sites = get_sites(sqlite_session, nif=None, limit=None, offset=0)

        assert [site.id for site in sites] == [12]

    def test_includes_archived_sites_when_requested(
        self, sqlite_session, db_factory, site_row_factory
    ) -> None:
        db_factory()
        archived = site_row_factory(
            id=13,
            city="Valencia",
            archived_at=datetime.now(UTC),
            archive_reason="closed",
        )
        sqlite_session.add(archived)
        sqlite_session.commit()

        sites = get_sites(
            sqlite_session,
            nif=None,
            limit=None,
            offset=0,
            include_archived=True,
        )

        returned_ids = {site.id for site in sites}
        assert returned_ids == {12, 13}

    def test_excludes_sites_when_client_is_archived_by_default(
        self, sqlite_session, db_factory, site_row_factory
    ) -> None:
        db_factory(
            client_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        sites = get_sites(sqlite_session, nif="A1234567B", limit=None, offset=0)

        assert sites is None

    def test_includes_sites_with_archived_client_when_requested(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            client_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        sites = get_sites(
            sqlite_session,
            nif=None,
            limit=None,
            offset=0,
            include_archived=True,
        )

        assert [site.id for site in sites] == [12]

    def test_filters_by_client_nif_when_client_exists(self) -> None:
        session = MagicMock()
        session.get.return_value = MagicMock(spec=Client)
        session.execute.return_value.scalars.return_value.all.return_value = []

        result = get_sites(session, nif="A1234567B", limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert result == []
        session.get.assert_called_once_with(Client, "A1234567B")
        assert "sites.nif = :nif_1" in str(stmt)

    def test_returns_none_when_client_filter_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_sites(session, nif="A1234567B", limit=None, offset=0)

        assert result is None
        session.get.assert_called_once_with(Client, "A1234567B")
        session.execute.assert_not_called()

    def test_excludes_certifications_when_site_is_archived_by_default(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            certification_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        certifications = get_certifications(
            sqlite_session,
            site_id=None,
            open_only=False,
            limit=None,
            offset=0,
        )

        assert certifications == []


class TestGetSiteById:
    def test_gets_site_by_id_from_session(self, sqlite_session, db_factory) -> None:
        db_factory()

        result = get_site_by_id(sqlite_session, 12)

        assert result.id == 12

    def test_raises_when_site_is_not_found(self, sqlite_session, db_factory) -> None:
        db_factory()

        with pytest.raises(SiteNotFoundError):
            get_site_by_id(sqlite_session, 999)

    def test_includes_archived_site_by_default(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            site_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        result = get_site_by_id(sqlite_session, 12)

        assert result is not None
        assert result.archive_reason == "closed"

    def test_returns_archived_site_when_requested(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            site_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        result = get_site_by_id(sqlite_session, 12, include_archived=True)

        assert result.id == 12
        assert result.archive_reason == "closed"


class TestPostNewSite:
    def test_adds_and_commits_new_site(self) -> None:
        session = MagicMock()
        site = _site_create()

        post_new_site(session, site)

        session.add.assert_called_once()
        added_site = session.add.call_args.args[0]

        assert isinstance(added_site, Site)
        assert added_site.nif == "A1234567B"
        assert added_site.city == "Madrid"
        assert added_site.postal_code == 28013
        assert added_site.street == "Gran Via"
        assert added_site.street_number is None
        assert added_site.suite is None
        assert added_site.address_info == "Main entrance"

    def test_rolls_back_and_raises_conflict_when_insert_conflicts(self) -> None:
        session = MagicMock()
        session.commit.side_effect = IntegrityError("insert failed", {}, None)
        site = _site_create()

        with pytest.raises(SiteConflictError):
            post_new_site(session, site)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()

    def test_raises_client_not_found_when_client_does_not_exist(
        self, monkeypatch
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = IntegrityError("insert failed", {}, None)
        site = _site_create()
        monkeypatch.setattr(
            "compliance.services.sites.crud.get_constraint_name",
            lambda exc: "fk_sites_nif_clients",
        )

        with pytest.raises(SiteClientNotFoundError):
            post_new_site(session, site)

        session.rollback.assert_called_once_with()


class TestGetSiteCertifications:
    def test_returns_certifications_for_site(self) -> None:
        session = MagicMock()
        expected_certifications = [
            MagicMock(spec=Certification),
            MagicMock(spec=Certification),
        ]
        session.execute.return_value.scalars.return_value.all.return_value = (
            expected_certifications
        )

        result = get_site_certifications(session, 12, limit=None, offset=0)

        session.execute.assert_called_once()
        assert result == expected_certifications

    def test_returns_empty_list_when_site_has_no_certifications(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        result = get_site_certifications(session, 999, limit=None, offset=0)

        session.execute.assert_called_once()
        assert result == []

    def test_orders_certifications_by_resolution_date_desc_then_id(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [
            MagicMock(spec=Certification)
        ]

        get_site_certifications(session, 12, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert "ORDER BY certifications.resolution_date DESC, certifications.id" in str(
            stmt
        )

    def test_applies_limit_and_offset_to_query(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [
            MagicMock(spec=Certification)
        ]

        get_site_certifications(session, 12, limit=10, offset=20)

        stmt = session.execute.call_args.args[0]
        statement_text = str(stmt)
        assert "LIMIT" in statement_text
        assert "OFFSET" in statement_text

    def test_excludes_archived_certifications_by_default(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_site_certifications(session, 12, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert "certifications.archived_at IS NULL" in str(stmt)
        assert "sites.archived_at IS NULL" in str(stmt)

    def test_raises_when_site_is_archived_by_default(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            site_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        with pytest.raises(SiteNotFoundError):
            get_site_certifications(sqlite_session, 12, limit=None, offset=0)

    def test_includes_archived_certifications_when_requested(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_site_certifications(
            session, 12, limit=None, offset=0, include_archived=True
        )

        stmt = session.execute.call_args.args[0]
        assert "certifications.archived_at IS NULL" not in str(stmt)
        assert "findings.archived_at IS NULL" not in str(stmt)
        assert "rules.archived_at IS NULL" not in str(stmt)
        assert "sites.archived_at IS NULL" not in str(stmt)


class TestFormatSiteCertifications:
    def test_wraps_certifications_in_site_response(
        self, certification_row_factory
    ) -> None:
        certifications = [certification_row_factory()]

        result = format_site_certifications(12, certifications)

        assert result == SiteCertificationsOut.model_validate(
            {"site_id": 12, "certifications": certifications}
        )


class TestGetSiteHistoryForSite:
    def test_returns_none_when_query_returns_no_rows(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_site_history(session, 71)

        session.execute.assert_called_once()
        assert result is None

    def test_formats_site_history_when_query_returns_rows(
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
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = rows

        result = get_site_history(session, 71)

        session.execute.assert_called_once()
        assert result == _format_site_history(rows)

    def test_excludes_archived_history_records_by_default(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_site_history(session, 71)

        stmt = session.execute.call_args.args[0]
        assert "certifications.archived_at IS NULL" in str(stmt)

    def test_includes_archived_history_records_when_requested(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_site_history(session, 71, include_archived=True)

        stmt = session.execute.call_args.args[0]
        assert "certifications.archived_at IS NULL" not in str(stmt)


class TestGetSiteAttachments:
    def test_returns_none_when_query_returns_no_rows(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_site_attachments(session, 71)

        session.execute.assert_called_once()
        assert result == SiteAttachmentsOut(site_id=71, attachments=[])

    def test_formats_site_attachments_when_query_returns_rows(
        self, attachment_out_factory
    ) -> None:
        rows = [attachment_out_factory()]
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = rows

        result = get_site_attachments(session, 71)

        session.execute.assert_called_once()
        assert result == _format_site_attachments(rows)

    def test_excludes_archived_attachments_by_default(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_site_attachments(session, 71)

        stmt = session.execute.call_args.args[0]
        assert "attachments.archived_at IS NULL" in str(stmt)
        assert "findings.archived_at IS NULL" in str(stmt)
        assert "rules.archived_at IS NULL" in str(stmt)
        assert "AND (findings.id IS NULL" not in str(stmt)
        assert "AND (rules.id IS NULL" not in str(stmt)

    def test_includes_archived_attachments_when_requested(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_site_attachments(session, 71, include_archived=True)

        stmt = session.execute.call_args.args[0]
        assert "attachments.archived_at IS NULL" not in str(stmt)
        assert "findings.archived_at IS NULL" not in str(stmt)
        assert "rules.archived_at IS NULL" not in str(stmt)

    def test_excludes_attachments_from_archived_sites_by_default(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            site_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        with pytest.raises(SiteNotFoundError):
            get_site_attachments(sqlite_session, 12)

    def test_excludes_attachments_from_archived_clients_by_default(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            client_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        with pytest.raises(SiteClientNotFoundError):
            get_site_attachments(sqlite_session, 12)


class TestFormatSiteHistory:
    def test_creates_site_history_with_certification_and_finding(
        self, site_history_row_factory
    ) -> None:
        result = _format_site_history([site_history_row_factory()])

        assert isinstance(result, SiteHistory)
        assert result.site_id == 71
        assert result.inspection_count == 1
        assert result.latest_inspection_date == date(2026, 4, 1)
        assert len(result.certifications) == 1
        assert result.certifications[0].cert_id == 100
        assert len(result.certifications[0].findings) == 1
        assert result.certifications[0].findings[0].finding_id == 1

    def test_appends_findings_to_existing_certification(
        self, site_history_row_factory
    ) -> None:
        rows = [
            site_history_row_factory(finding_id=1, finding="Missing document"),
            site_history_row_factory(finding_id=2, finding="Incomplete record"),
        ]

        result = _format_site_history(rows)

        assert len(result.certifications) == 1
        assert [
            finding.finding_id for finding in result.certifications[0].findings
        ] == [
            1,
            2,
        ]

    def test_groups_certifications_by_id_without_reordering(
        self, site_history_row_factory
    ) -> None:
        rows = [
            site_history_row_factory(
                cert_id=200, finding_id=2, finding="Second cert finding"
            ),
            site_history_row_factory(
                cert_id=100, finding_id=1, finding="First cert finding"
            ),
            site_history_row_factory(
                cert_id=200,
                finding_id=3,
                finding="Another second cert finding",
            ),
        ]

        result = _format_site_history(rows)

        assert [cert.cert_id for cert in result.certifications] == [200, 100]
        assert [
            finding.finding_id for finding in result.certifications[0].findings
        ] == [2, 3]


class TestBuildFindingHistoryFromSiteHistory:
    def test_builds_finding_history_from_row(self, site_history_row_factory) -> None:
        result = _build_finding_history_from_site_history(site_history_row_factory())

        assert isinstance(result, FindingHistory)
        assert result.finding_id == 1
        assert result.rule_index == "7 CFR 205.201"

    def test_raises_key_error_when_required_finding_field_is_missing(
        self, site_history_row_factory
    ) -> None:
        row = site_history_row_factory()
        del row["rule_description"]

        with pytest.raises(KeyError, match="Missing finding fields"):
            _build_finding_history_from_site_history(row)


class TestBuildFindingHistoryFromSiteAttachmentsOut:
    def test_builds_finding_history_from_nested_row_objects(
        self, attachment_out_factory
    ) -> None:
        result = _build_finding_history_from_site_attachments(attachment_out_factory())

        assert result == FindingHistory(
            finding_id=1,
            finding="Missing document",
            rule_index="7 CFR 205.201",
            rule_title="Organic plan",
            rule_description="Producer must maintain an organic system plan.",
        )

    def test_raises_key_error_when_required_row_object_is_missing(
        self, attachment_out_factory
    ) -> None:
        row = attachment_out_factory()
        del row["Rule"]

        with pytest.raises(KeyError, match="Missing finding history fields"):
            _build_finding_history_from_site_attachments(row)

    def test_raises_key_error_when_required_finding_history_field_is_missing(
        self, attachment_out_factory
    ) -> None:
        row = attachment_out_factory(
            Rule=SimpleNamespace(
                rule_index="7 CFR 205.201",
                title="Organic plan",
            )
        )

        with pytest.raises(KeyError, match="rule_description"):
            _build_finding_history_from_site_attachments(row)


class TestFormatSiteAttachmentsOut:
    def test_creates_site_attachments_with_finding_link(
        self, attachment_out_factory
    ) -> None:
        result = _format_site_attachments([attachment_out_factory()])

        assert result.site_id == 71
        assert len(result.attachments) == 1
        assert result.attachments[0].id == 50
        assert result.attachments[0].regulation_title == "USDA Organic"
        assert len(result.attachments[0].finding_links) == 1
        assert result.attachments[0].finding_links[0].finding_id == 1

    def test_groups_multiple_findings_under_same_attachment(
        self, attachment_out_factory
    ) -> None:
        rows = [
            attachment_out_factory(),
            attachment_out_factory(
                Finding=SimpleNamespace(id=2, finding="Incomplete record"),
                Rule=SimpleNamespace(
                    rule_index="7 CFR 205.202",
                    title="Land requirements",
                    description="Land must meet organic requirements.",
                ),
            ),
        ]

        result = _format_site_attachments(rows)

        assert len(result.attachments) == 1
        assert [
            finding.finding_id for finding in result.attachments[0].finding_links
        ] == [1, 2]

    def test_groups_attachments_by_id_without_reordering(
        self, attachment_out_factory, attachment_row_factory
    ) -> None:
        second_attachment = attachment_row_factory(
            id=60,
            certification_id=100,
        )
        rows = [
            attachment_out_factory(Attachment=second_attachment),
            attachment_out_factory(),
            attachment_out_factory(
                Attachment=second_attachment,
                Finding=SimpleNamespace(id=2, finding="Incomplete record"),
                Rule=SimpleNamespace(
                    rule_index="7 CFR 205.202",
                    title="Land requirements",
                    description="Land must meet organic requirements.",
                ),
            ),
        ]

        result = _format_site_attachments(rows)

        assert [attachment.id for attachment in result.attachments] == [60, 50]
        assert [
            finding.finding_id for finding in result.attachments[0].finding_links
        ] == [1, 2]

    def test_raises_stop_iteration_when_rows_are_empty(self) -> None:
        with pytest.raises(StopIteration):
            _format_site_attachments([])

    def test_raises_value_error_when_first_row_is_empty(self) -> None:
        with pytest.raises(ValueError, match="First attachment row is empty"):
            _format_site_attachments([{}])


class TestPostSiteArchivedById:
    def test_archives_site_with_stripped_reason(self, site_row_factory) -> None:
        session = MagicMock()
        site = site_row_factory()
        session.get.return_value = site

        result = post_site_archived_by_id(
            session,
            71,
            archive_request=ArchiveRequest(archive_reason="  duplicate  "),
        )

        assert result is site
        assert site.archived_at is not None
        assert site.archived_at.tzinfo is UTC
        assert site.archive_reason == "duplicate"
        session.get.assert_called_once_with(Site, 71)
        session.commit.assert_called_once_with()

    def test_does_not_rearchive_existing_archived_site(self, site_row_factory) -> None:
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)
        session = MagicMock()
        site = site_row_factory(archived_at=archived_at, archive_reason="old")
        session.get.return_value = site

        result = post_site_archived_by_id(
            session, 71, archive_request=ArchiveRequest(archive_reason="new")
        )

        assert result is site
        assert site.archived_at == archived_at
        assert site.archive_reason == "old"
        session.commit.assert_not_called()

    def test_returns_none_when_site_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_site_archived_by_id(session, 71, archive_request=ArchiveRequest())

        assert result is None
        session.get.assert_called_once_with(Site, 71)
        session.commit.assert_not_called()


class TestPostSiteRestoredById:
    def test_restores_archived_site(self, site_row_factory) -> None:
        session = MagicMock()
        site = site_row_factory(
            archived_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
            archive_reason="old",
        )
        session.get.return_value = site

        result = post_site_restored_by_id(session, 71)

        assert result is site
        assert site.archived_at is None
        assert site.archive_reason is None
        session.get.assert_called_once_with(Site, 71)
        session.commit.assert_called_once_with()

    def test_returns_active_site_without_commit(self, site_row_factory) -> None:
        session = MagicMock()
        site = site_row_factory(archived_at=None, archive_reason=None)
        session.get.return_value = site

        result = post_site_restored_by_id(session, 71)

        assert result is site
        session.commit.assert_not_called()

    def test_returns_none_when_site_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_site_restored_by_id(session, 71)

        assert result is None
        session.get.assert_called_once_with(Site, 71)
        session.commit.assert_not_called()


class TestPostSiteArchiveRestoreIntegration:
    def test_archive_then_restore_works(self, sqlite_session, db_factory) -> None:
        db_factory()
        archived = post_site_archived_by_id(
            sqlite_session,
            12,
            archive_request=ArchiveRequest(archive_reason=" duplicate "),
        )
        archived = post_site_archived_by_id(
            sqlite_session,
            12,
            archive_request=ArchiveRequest(archive_reason=" second "),
        )
        assert archived is not None
        assert archived.archived_at is not None
        assert archived.archive_reason == "duplicate"

        restored = post_site_restored_by_id(sqlite_session, 12)

        assert restored is not None
        assert restored.archived_at is None
        assert restored.archive_reason is None
