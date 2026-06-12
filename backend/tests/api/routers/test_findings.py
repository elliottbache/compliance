from datetime import UTC, datetime

import pytest
from compliance.api.routers import findings as findings_router
from fastapi import HTTPException


class TestGetFindingsRouteClient:
    def test_route_returns_findings_json(
        self, main_module, client, mock_db, monkeypatch, finding_factory
    ):
        def fake_get_findings(
            session,
            *,
            site_id,
            certification_id,
            rule_id,
            attachment_id,
            open_only,
            include_archived=False,
        ):
            assert session is mock_db
            assert site_id is None
            assert certification_id is None
            assert rule_id is None
            assert attachment_id is None
            assert open_only is False
            return [finding_factory()]

        monkeypatch.setattr(findings_router, "get_findings", fake_get_findings)

        response = client.get("/findings")

        assert response.status_code == 200
        assert response.json() == [
            {
                "finding_id": 1,
                "finding": "Missing document",
                "site_id": 12,
                "certification_id": 100,
                "certification_title": "USDA Organic",
                "certification_resolution_date": "2026-04-15",
                "rule_id": 5,
                "rule_index": "7 CFR 205.201",
                "rule_title": "Organic plan",
                "rule_description": "Producer must maintain an organic system plan.",
                "attachments": [],
                "archived_at": None,
                "archive_reason": None,
            }
        ]

    def test_route_passes_query_filters_to_service(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_findings(
            session,
            *,
            site_id,
            certification_id,
            rule_id,
            attachment_id,
            open_only,
            include_archived=False,
        ):
            assert session is mock_db
            assert site_id == 12
            assert certification_id == 100
            assert rule_id == 5
            assert attachment_id == 50
            assert open_only is True
            return []

        monkeypatch.setattr(findings_router, "get_findings", fake_get_findings)

        response = client.get(
            "/findings?site_id=12&certification_id=100"
            "&rule_id=5&attachment_id=50&open_only=true"
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_route_excludes_archived_findings_by_default(
        self, client, mock_db, monkeypatch, finding_factory
    ):
        archived_finding_id = 2

        def fake_get_findings(
            session,
            *,
            site_id,
            certification_id,
            rule_id,
            attachment_id,
            open_only,
            include_archived=False,
        ):
            assert session is mock_db
            assert include_archived is False
            return [finding_factory()]

        monkeypatch.setattr(findings_router, "get_findings", fake_get_findings)

        response = client.get("/findings")

        assert response.status_code == 200
        returned_ids = {finding["finding_id"] for finding in response.json()}
        assert 1 in returned_ids
        assert archived_finding_id not in returned_ids

    def test_route_include_archived_returns_archived_finding(
        self, client, mock_db, monkeypatch, finding_factory
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)
        archived_finding_id = 2

        def fake_get_findings(
            session,
            *,
            site_id,
            certification_id,
            rule_id,
            attachment_id,
            open_only,
            include_archived=False,
        ):
            assert session is mock_db
            assert include_archived is True
            return [
                finding_factory(),
                finding_factory(
                    finding_id=archived_finding_id,
                    archived_at=archived_at,
                    archive_reason="resolved",
                ),
            ]

        monkeypatch.setattr(findings_router, "get_findings", fake_get_findings)

        response = client.get("/findings?include_archived=true")

        assert response.status_code == 200
        returned_ids = {finding["finding_id"] for finding in response.json()}
        assert archived_finding_id in returned_ids

    def test_route_returns_422_when_filter_type_is_invalid(self, client):
        response = client.get("/findings?site_id=not-an-int")

        assert response.status_code == 422


class TestGetFindingsRouteUnit:

    def test_returns_findings_from_service(
        self, main_module, monkeypatch, finding_factory
    ) -> None:
        fake_session = object()
        expected = [finding_factory()]

        def fake_get_findings(
            session,
            *,
            site_id,
            certification_id,
            rule_id,
            attachment_id,
            open_only,
            include_archived=False,
        ):
            assert session is fake_session
            assert site_id == 12
            assert certification_id == 100
            assert rule_id == 5
            assert attachment_id == 50
            assert open_only is True
            return expected

        monkeypatch.setattr(findings_router, "get_findings", fake_get_findings)

        result = findings_router.get_findings_route(
            fake_session,
            site_id=12,
            certification_id=100,
            rule_id=5,
            attachment_id=50,
            open_only=True,
        )

        assert result == expected

    def test_returns_404_when_site_filter_does_not_exist(self, monkeypatch) -> None:
        def fake_get_findings(
            session,
            *,
            site_id,
            certification_id,
            rule_id,
            attachment_id,
            open_only,
            include_archived=False,
        ):
            raise findings_router.FindingMissingSiteError(site_id)

        monkeypatch.setattr(findings_router, "get_findings", fake_get_findings)

        with pytest.raises(HTTPException) as exc_info:
            findings_router.get_findings_route(object(), site_id=999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Missing site 999."

    def test_returns_404_when_certification_filter_does_not_exist(
        self, monkeypatch
    ) -> None:
        def fake_get_findings(
            session,
            *,
            site_id,
            certification_id,
            rule_id,
            attachment_id,
            open_only,
            include_archived=False,
        ):
            raise findings_router.FindingMissingCertificationError(certification_id)

        monkeypatch.setattr(findings_router, "get_findings", fake_get_findings)

        with pytest.raises(HTTPException) as exc_info:
            findings_router.get_findings_route(object(), certification_id=999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Missing certification 999."

    def test_returns_404_when_rule_filter_does_not_exist(self, monkeypatch) -> None:
        def fake_get_findings(
            session,
            *,
            site_id,
            certification_id,
            rule_id,
            attachment_id,
            open_only,
            include_archived=False,
        ):
            raise findings_router.FindingMissingRuleError(rule_id)

        monkeypatch.setattr(findings_router, "get_findings", fake_get_findings)

        with pytest.raises(HTTPException) as exc_info:
            findings_router.get_findings_route(object(), rule_id=999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Missing rule 999."

    def test_returns_404_when_attachment_filter_does_not_exist(
        self, monkeypatch
    ) -> None:
        def fake_get_findings(
            session,
            *,
            site_id,
            certification_id,
            rule_id,
            attachment_id,
            open_only,
            include_archived=False,
        ):
            raise findings_router.FindingMissingAttachmentError(attachment_id)

        monkeypatch.setattr(findings_router, "get_findings", fake_get_findings)

        with pytest.raises(HTTPException) as exc_info:
            findings_router.get_findings_route(object(), attachment_id=999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Missing attachment 999."

    def test_registers_findings_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/findings"
        )

        assert route.response_model == list[findings_router.FindingOut]


class TestPostNewFindingRouteClient:
    def test_route_returns_created_finding_json(
        self, client, mock_db, monkeypatch, finding_factory
    ):
        expected_finding = finding_factory()

        def fake_post_new_finding(session, finding):
            assert session is mock_db
            assert finding.certification_id == 100
            assert finding.rule_id == 5
            assert finding.finding == "Missing document"
            return expected_finding

        monkeypatch.setattr(findings_router, "post_new_finding", fake_post_new_finding)

        response = client.post(
            "/findings",
            json={
                "certification_id": 100,
                "rule_id": 5,
                "finding": "Missing document",
            },
        )

        assert response.status_code == 201
        assert response.json() == {
            "finding_id": 1,
            "finding": "Missing document",
            "site_id": 12,
            "certification_id": 100,
            "certification_title": "USDA Organic",
            "certification_resolution_date": "2026-04-15",
            "rule_id": 5,
            "rule_index": "7 CFR 205.201",
            "rule_title": "Organic plan",
            "rule_description": "Producer must maintain an organic system plan.",
            "attachments": [],
            "archived_at": None,
            "archive_reason": None,
        }

    def test_route_returns_422_when_body_is_invalid(self, client):
        response = client.post(
            "/findings",
            json={
                "certification_id": 100,
                "finding": "Missing document",
            },
        )

        assert response.status_code == 422


class TestPostNewFindingRouteUnit:

    def test_returns_created_finding(self, monkeypatch, finding_factory) -> None:
        fake_session = object()
        finding = findings_router.FindingCreate(
            certification_id=100,
            rule_id=5,
            finding="Missing document",
        )
        expected_finding = finding_factory()

        def fake_post_new_finding(session, finding_info):
            assert finding_info is finding
            assert session is fake_session
            return expected_finding

        monkeypatch.setattr(findings_router, "post_new_finding", fake_post_new_finding)

        result = findings_router.post_new_finding_route(fake_session, finding)

        assert result == findings_router.FindingOut.model_validate(expected_finding)

    def test_returns_404_when_certification_does_not_exist(self, monkeypatch) -> None:
        finding = findings_router.FindingCreate(
            certification_id=100,
            rule_id=5,
            finding="Missing document",
        )

        def fake_post_new_finding(session, finding_info):
            raise findings_router.FindingMissingCertificationError(
                finding_info.certification_id
            )

        monkeypatch.setattr(findings_router, "post_new_finding", fake_post_new_finding)

        with pytest.raises(HTTPException) as exc_info:
            findings_router.post_new_finding_route(object(), finding)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Certification 100 does not exist."

    def test_returns_404_when_rule_does_not_exist(self, monkeypatch) -> None:
        finding = findings_router.FindingCreate(
            certification_id=100,
            rule_id=5,
            finding="Missing document",
        )

        def fake_post_new_finding(session, finding_info):
            raise findings_router.FindingMissingRuleError(finding_info.rule_id)

        monkeypatch.setattr(findings_router, "post_new_finding", fake_post_new_finding)

        with pytest.raises(HTTPException) as exc_info:
            findings_router.post_new_finding_route(object(), finding)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Rule 5 does not exist."

    def test_returns_409_when_finding_conflicts(self, monkeypatch) -> None:
        finding = findings_router.FindingCreate(
            certification_id=100,
            rule_id=5,
            finding="Missing document",
        )

        def fake_post_new_finding(session, finding_info):
            raise findings_router.FindingConflictError()

        monkeypatch.setattr(findings_router, "post_new_finding", fake_post_new_finding)

        with pytest.raises(HTTPException) as exc_info:
            findings_router.post_new_finding_route(object(), finding)

        assert exc_info.value.status_code == 409
        assert "Finding was not added" in exc_info.value.detail

    def test_registers_finding_create_response_model_and_created_status(
        self, main_module
    ) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/findings"
            and "POST" in getattr(route, "methods", set())
        )

        assert route.response_model is findings_router.FindingOut
        assert route.status_code == 201


class TestPostFindingArchivedByIdRouteClient:
    # TestClient
    def test_route_archives_active_finding(
        self, client, mock_db, monkeypatch, finding_factory, assert_archived_response
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)

        def fake_post_finding_archived_by_id(session, finding_id, *, archive_request):
            assert session is mock_db
            assert finding_id == 1
            assert archive_request.archive_reason == "duplicate"
            return finding_factory(archived_at=archived_at, archive_reason="duplicate")

        monkeypatch.setattr(
            findings_router,
            "post_finding_archived_by_id",
            fake_post_finding_archived_by_id,
        )

        response = client.post(
            "/findings/1/archive", json={"archive_reason": "duplicate"}
        )

        assert response.status_code == 200
        assert_archived_response(response.json(), "duplicate")

    def test_route_archive_already_archived_finding_returns_200(
        self, client, mock_db, monkeypatch, finding_factory, assert_archived_response
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)

        def fake_post_finding_archived_by_id(session, finding_id, *, archive_request):
            assert session is mock_db
            assert finding_id == 1
            return finding_factory(archived_at=archived_at, archive_reason="old reason")

        monkeypatch.setattr(
            findings_router,
            "post_finding_archived_by_id",
            fake_post_finding_archived_by_id,
        )

        response = client.post(
            "/findings/1/archive", json={"archive_reason": "old reason"}
        )

        assert response.status_code == 200
        assert_archived_response(response.json())

    def test_route_returns_404_when_finding_does_not_exist(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_finding_archived_by_id(session, finding_id, *, archive_request):
            assert session is mock_db
            assert finding_id == 1
            return None

        monkeypatch.setattr(
            findings_router,
            "post_finding_archived_by_id",
            fake_post_finding_archived_by_id,
        )

        response = client.post("/findings/1/archive")

        assert response.status_code == 404
        assert response.json() == {"detail": "Finding does not exist: 1."}

    def test_route_returns_422_when_finding_id_is_invalid(self, client):
        response = client.post("/findings/not-an-id/archive")

        assert response.status_code == 422


class TestPostFindingArchivedByIdRouteUnit:

    def test_defaults_missing_archive_request(self, monkeypatch) -> None:
        fake_session = object()
        expected = findings_router.FindingOut(
            finding_id=1,
            finding="Missing document",
            site_id=12,
            certification_id=100,
            certification_title="USDA Organic",
            certification_resolution_date=None,
            rule_id=5,
            rule_index="7 CFR 205.201",
            rule_title="Organic plan",
            rule_description="Producer must maintain an organic system plan.",
            attachments=[],
            archived_at=None,
            archive_reason=None,
        )

        def fake_post_finding_archived_by_id(session, finding_id, *, archive_request):
            assert session is fake_session
            assert finding_id == 1
            assert archive_request == findings_router.ArchiveRequest()
            return expected

        monkeypatch.setattr(
            findings_router,
            "post_finding_archived_by_id",
            fake_post_finding_archived_by_id,
        )

        result = findings_router.post_finding_archived_by_id_route(fake_session, 1)

        assert result == expected

    def test_returns_404_when_finding_does_not_exist(self, monkeypatch) -> None:
        def fake_post_finding_archived_by_id(session, finding_id, *, archive_request):
            return None

        monkeypatch.setattr(
            findings_router,
            "post_finding_archived_by_id",
            fake_post_finding_archived_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            findings_router.post_finding_archived_by_id_route(object(), 1)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Finding does not exist: 1."


class TestPostFindingRestoredByIdRouteClient:
    # TestClient
    def test_route_restores_archived_finding(
        self, client, mock_db, monkeypatch, finding_factory, assert_restored_response
    ):
        def fake_post_finding_restored_by_id(session, finding_id):
            assert session is mock_db
            assert finding_id == 1
            return finding_factory(archived_at=None, archive_reason=None)

        monkeypatch.setattr(
            findings_router,
            "post_finding_restored_by_id",
            fake_post_finding_restored_by_id,
        )

        response = client.post("/findings/1/restore")

        assert response.status_code == 200
        response_json = response.json()
        assert_restored_response(response_json)

    def test_route_restore_active_finding_returns_200(
        self, client, mock_db, monkeypatch, finding_factory, assert_restored_response
    ):
        def fake_post_finding_restored_by_id(session, finding_id):
            assert session is mock_db
            assert finding_id == 1
            return finding_factory(archived_at=None, archive_reason=None)

        monkeypatch.setattr(
            findings_router,
            "post_finding_restored_by_id",
            fake_post_finding_restored_by_id,
        )

        response = client.post("/findings/1/restore")

        assert response.status_code == 200
        assert_restored_response(response.json())

    def test_route_returns_404_when_finding_does_not_exist(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_finding_restored_by_id(session, finding_id):
            assert session is mock_db
            assert finding_id == 1
            return None

        monkeypatch.setattr(
            findings_router,
            "post_finding_restored_by_id",
            fake_post_finding_restored_by_id,
        )

        response = client.post("/findings/1/restore")

        assert response.status_code == 404
        assert response.json() == {"detail": "Finding does not exist: 1."}

    def test_route_returns_422_when_finding_id_is_invalid(self, client):
        response = client.post("/findings/not-an-id/restore")

        assert response.status_code == 422


class TestPostFindingRestoredByIdRouteUnit:

    def test_returns_restored_finding(self, monkeypatch) -> None:
        fake_session = object()
        expected = findings_router.FindingOut(
            finding_id=1,
            finding="Missing document",
            site_id=12,
            certification_id=100,
            certification_title="USDA Organic",
            certification_resolution_date=None,
            rule_id=5,
            rule_index="7 CFR 205.201",
            rule_title="Organic plan",
            rule_description="Producer must maintain an organic system plan.",
            attachments=[],
            archived_at=None,
            archive_reason=None,
        )

        def fake_post_finding_restored_by_id(session, finding_id):
            assert session is fake_session
            assert finding_id == 1
            return expected

        monkeypatch.setattr(
            findings_router,
            "post_finding_restored_by_id",
            fake_post_finding_restored_by_id,
        )

        result = findings_router.post_finding_restored_by_id_route(fake_session, 1)

        assert result == expected

    def test_returns_404_when_finding_does_not_exist(self, monkeypatch) -> None:
        def fake_post_finding_restored_by_id(session, finding_id):
            return None

        monkeypatch.setattr(
            findings_router,
            "post_finding_restored_by_id",
            fake_post_finding_restored_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            findings_router.post_finding_restored_by_id_route(object(), 1)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Finding does not exist: 1."
