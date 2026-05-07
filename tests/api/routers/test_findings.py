import pytest
from fastapi import HTTPException

from compliance.api.routers import findings as findings_router


class TestGetFindingsRoute:
    def test_client_returns_findings_json(
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
            }
        ]

    def test_client_passes_query_filters_to_service(
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

    def test_client_returns_422_when_filter_type_is_invalid(self, client):
        response = client.get("/findings?site_id=not-an-int")

        assert response.status_code == 422

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


class TestPostNewFindingRoute:
    def test_client_returns_created_finding_json(
        self, client, mock_db, monkeypatch, finding_factory
    ):
        expected_finding = finding_factory()

        def fake_post_new_finding(finding, session):
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

    def test_client_returns_422_when_body_is_invalid(self, client):
        response = client.post(
            "/findings",
            json={
                "certification_id": 100,
                "finding": "Missing document",
            },
        )

        assert response.status_code == 422

    def test_returns_created_finding(self, monkeypatch, finding_factory) -> None:
        fake_session = object()
        finding = findings_router.FindingCreate(
            certification_id=100,
            rule_id=5,
            finding="Missing document",
        )
        expected_finding = finding_factory()

        def fake_post_new_finding(finding_info, session):
            assert finding_info is finding
            assert session is fake_session
            return expected_finding

        monkeypatch.setattr(findings_router, "post_new_finding", fake_post_new_finding)

        result = findings_router.post_new_finding_route(finding, fake_session)

        assert result == findings_router.FindingOut.model_validate(expected_finding)

    def test_returns_404_when_certification_does_not_exist(self, monkeypatch) -> None:
        finding = findings_router.FindingCreate(
            certification_id=100,
            rule_id=5,
            finding="Missing document",
        )

        def fake_post_new_finding(finding_info, session):
            raise findings_router.FindingMissingCertificationError(
                finding_info.certification_id
            )

        monkeypatch.setattr(findings_router, "post_new_finding", fake_post_new_finding)

        with pytest.raises(HTTPException) as exc_info:
            findings_router.post_new_finding_route(finding, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Certification 100 does not exist."

    def test_returns_404_when_rule_does_not_exist(self, monkeypatch) -> None:
        finding = findings_router.FindingCreate(
            certification_id=100,
            rule_id=5,
            finding="Missing document",
        )

        def fake_post_new_finding(finding_info, session):
            raise findings_router.FindingMissingRuleError(finding_info.rule_id)

        monkeypatch.setattr(findings_router, "post_new_finding", fake_post_new_finding)

        with pytest.raises(HTTPException) as exc_info:
            findings_router.post_new_finding_route(finding, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Rule 5 does not exist."

    def test_returns_409_when_finding_conflicts(self, monkeypatch) -> None:
        finding = findings_router.FindingCreate(
            certification_id=100,
            rule_id=5,
            finding="Missing document",
        )

        def fake_post_new_finding(finding_info, session):
            raise findings_router.FindingConflictError()

        monkeypatch.setattr(findings_router, "post_new_finding", fake_post_new_finding)

        with pytest.raises(HTTPException) as exc_info:
            findings_router.post_new_finding_route(finding, object())

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
