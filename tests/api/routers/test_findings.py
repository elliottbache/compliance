from datetime import date

from compliance.api.routers import findings as findings_router


def finding_factory(**overrides):
    """Build a finding response payload for route tests."""
    data = {
        "finding_id": 1,
        "finding": "Missing document",
        "site_id": 12,
        "certification_id": 100,
        "certification_title": "USDA Organic",
        "certification_resolution_date": date(2026, 4, 15),
        "rule_id": 5,
        "rule_index": "7 CFR 205.201",
        "rule_title": "Organic plan",
        "rule_description": "Producer must maintain an organic system plan.",
    }
    data.update(overrides)
    return findings_router.FindingOut.model_validate(data)


class TestGetFindingsRoute:
    def test_client_returns_findings_json(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_findings(session, site_id, rule_id, open_only):
            assert session is mock_db
            assert site_id is None
            assert rule_id is None
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
            }
        ]

    def test_client_passes_query_filters_to_service(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_findings(session, site_id, rule_id, open_only):
            assert session is mock_db
            assert site_id == 12
            assert rule_id == 5
            assert open_only is True
            return []

        monkeypatch.setattr(findings_router, "get_findings", fake_get_findings)

        response = client.get("/findings?site_id=12&rule_id=5&open_only=true")

        assert response.status_code == 200
        assert response.json() == []

    def test_client_returns_422_when_filter_type_is_invalid(self, client):
        response = client.get("/findings?site_id=not-an-int")

        assert response.status_code == 422

    def test_returns_findings_from_service(self, main_module, monkeypatch) -> None:
        fake_session = object()
        expected = [finding_factory()]

        def fake_get_findings(session, site_id, rule_id, open_only):
            assert session is fake_session
            assert site_id == 12
            assert rule_id == 5
            assert open_only is True
            return expected

        monkeypatch.setattr(findings_router, "get_findings", fake_get_findings)

        result = findings_router.get_findings_route(
            fake_session, site_id=12, rule_id=5, open_only=True
        )

        assert result == expected

    def test_registers_findings_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/findings"
        )

        assert route.response_model == list[findings_router.FindingOut]
