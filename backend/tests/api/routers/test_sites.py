from datetime import UTC, datetime

import pytest
from compliance.api.routers import sites as sites_router
from fastapi import HTTPException
from httpx import Request


@pytest.mark.usefixtures("viewer_user_override")
class TestGetSitesRouteClient:
    # TestClient
    def test_route_returns_site_json(self, client, mock_db, monkeypatch, site_factory):
        def fake_get_sites(session, *, nif, limit, offset, include_archived=False):
            assert session is mock_db
            assert nif is None
            assert limit == 2
            assert offset == 1
            return [
                site_factory(),
                site_factory(
                    id=13,
                    city="Valencia",
                    postal_code=46001,
                    street="Carrer de Colon",  # codespell:ignore carrer
                ),
            ]

        monkeypatch.setattr(sites_router, "get_sites", fake_get_sites)

        response = client.get("/sites?limit=2&offset=1")

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": 12,
                "nif": "A1234567B",
                "city": "Madrid",
                "postal_code": 28013,
                "street": "Gran Via",
                "street_number": None,
                "suite": None,
                "address_info": "Main entrance",
                "archived_at": None,
                "archive_reason": None,
            },
            {
                "id": 13,
                "nif": "A1234567B",
                "city": "Valencia",
                "postal_code": 46001,
                "street": "Carrer de Colon",  # codespell:ignore carrer
                "street_number": None,
                "suite": None,
                "address_info": "Main entrance",
                "archived_at": None,
                "archive_reason": None,
            },
        ]

    def test_route_excludes_archived_sites_by_default(
        self, client, mock_db, monkeypatch, site_factory
    ):
        archived_site_id = 13

        def fake_get_sites(session, *, nif, limit, offset, include_archived=False):
            assert session is mock_db
            assert include_archived is False
            return [site_factory()]

        monkeypatch.setattr(sites_router, "get_sites", fake_get_sites)

        response = client.get("/sites")

        assert response.status_code == 200
        returned_ids = {site["id"] for site in response.json()}
        assert 12 in returned_ids
        assert archived_site_id not in returned_ids

    def test_route_include_archived_returns_archived_site(
        self, client, mock_db, monkeypatch, site_factory
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)
        archived_site_id = 13

        def fake_get_sites(session, *, nif, limit, offset, include_archived=False):
            assert session is mock_db
            assert include_archived is True
            return [
                site_factory(),
                site_factory(
                    id=archived_site_id,
                    city="Valencia",
                    postal_code=46001,
                    archived_at=archived_at,
                    archive_reason="closed",
                ),
            ]

        monkeypatch.setattr(sites_router, "get_sites", fake_get_sites)

        response = client.get("/sites?include_archived=true")

        assert response.status_code == 200
        returned_ids = {site["id"] for site in response.json()}
        assert archived_site_id in returned_ids

    def test_route_returns_422_when_limit_is_invalid(self, client):
        response = client.get("/sites?limit=0")

        assert response.status_code == 422


class TestGetSitesRouteUnit:
    def test_returns_sites(self, monkeypatch, site_factory) -> None:
        fake_session = object()
        sites = [site_factory()]
        expected_sites = [sites_router.SiteOut.model_validate(site) for site in sites]

        def fake_get_sites(session, *, nif, limit, offset, include_archived=False):
            assert session is fake_session
            assert nif == "A1234567B"
            assert limit == 10
            assert offset == 5
            return sites

        monkeypatch.setattr(sites_router, "get_sites", fake_get_sites)

        result = sites_router.get_sites_route(
            fake_session,
            _authorized_user=object(),
            nif="A1234567B",
            limit=10,
            offset=5,
        )

        assert result == expected_sites

    def test_returns_404_when_client_filter_does_not_exist(self, monkeypatch) -> None:
        def fake_get_sites(session, *, nif, limit, offset, include_archived=False):
            assert nif == "A1234567B"
            return None

        monkeypatch.setattr(sites_router, "get_sites", fake_get_sites)

        with pytest.raises(HTTPException) as exc_info:
            sites_router.get_sites_route(
                object(),
                _authorized_user=object(),
                nif="A1234567B",
                limit=None,
                offset=0,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No client with this NIF: A1234567B."

    def test_registers_site_list_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites"
            and "GET" in getattr(route, "methods", set())
        )

        assert route.response_model == list[sites_router.SiteOut]


@pytest.mark.usefixtures("viewer_user_override")
class TestGetSiteHistoryRouteClient:
    # TestClient
    def test_route_returns_site_history_json_when_found(
        self, main_module, client, mock_db, monkeypatch, site_history_factory
    ):
        def fake_get_site_history(session, site_id, *, include_archived=False):
            assert site_id == 12
            assert session is mock_db
            return site_history_factory()

        monkeypatch.setattr(sites_router, "get_site_history", fake_get_site_history)

        response = client.get("/sites/12/history")

        assert response.status_code == 200
        assert response.json() == {
            "site_id": 101,
            "certifications": [
                {
                    "cert_id": 5001,
                    "result": "Pass",
                    "resolution_date": "2023-10-20",
                    "reg_title": "Fire Safety 2023",
                    "reg_description": "Standard fire safety regulations for commercial buildings.",
                    "certifier_org_name": "SafeCheck Inc.",
                    "inspection_date": "2023-10-15",
                    "findings": [
                        {
                            "finding_id": 901,
                            "finding": "Extinguisher pressure low",
                            "rule_index": "FS-101",
                            "rule_title": "Equipment Maintenance",
                            "rule_description": "Extinguishers must be within safe pressure limits.",
                        }
                    ],
                },
                {
                    "cert_id": 5002,
                    "result": None,
                    "resolution_date": None,
                    "reg_title": "Electrical Safety",
                    "reg_description": "General electrical standards.",
                    "certifier_org_name": "VoltGuard",
                    "inspection_date": "2023-11-05",
                    "findings": [],
                },
            ],
            "inspection_count": 2,
            "latest_inspection_date": "2023-11-05",
        }

    def test_route_returns_404_when_site_is_not_found(
        self, client, mock_db, monkeypatch
    ):
        fake_site = None

        def fake_get_site_history(session, site_id, *, include_archived=False):
            assert site_id == 999
            assert session is mock_db
            return fake_site

        monkeypatch.setattr(sites_router, "get_site_history", fake_get_site_history)

        response = client.get("/sites/999/history")

        assert response.status_code == 404
        assert response.json() == {"detail": "No site history found for this id: 999"}

    def test_route_returns_422_when_site_id_is_not_an_int(
        self, client, mock_db, monkeypatch, site_history_factory
    ):
        def fake_get_site_history(session, site_id, *, include_archived=False):
            assert site_id == 12
            assert session is mock_db
            return site_history_factory()

        monkeypatch.setattr(sites_router, "get_site_history", fake_get_site_history)

        response = client.get("/sites/not-an-int/history")

        assert response.status_code == 422


class TestGetSiteHistoryRouteUnit:
    def test_returns_site_history_when_found(self, monkeypatch) -> None:
        fake_session = object()
        site_history = sites_router.SiteHistory(
            site_id=12,
            certifications=[],
            inspection_count=0,
            latest_inspection_date=None,
        )

        def fake_get_site_history(session, site_id, *, include_archived=False):
            assert site_id == 12
            assert session is fake_session
            return site_history

        monkeypatch.setattr(
            sites_router,
            "get_site_history",
            fake_get_site_history,
        )

        result = sites_router.get_site_history_route(
            fake_session,
            _authorized_user=object(),
            site_id=12,
        )

        assert result == site_history

    def test_returns_404_when_site_history_is_not_found(self, monkeypatch) -> None:
        def fake_get_site_history(session, site_id, *, include_archived=False):
            return None

        monkeypatch.setattr(
            sites_router,
            "get_site_history",
            fake_get_site_history,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router.get_site_history_route(
                object(),
                _authorized_user=object(),
                site_id=999,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No site history found for this id: 999"

    def test_registers_site_history_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/history"
        )

        assert route.response_model is sites_router.SiteHistory


@pytest.mark.usefixtures("admin_user_override")
class TestPostNewSiteRouteClient:
    # TestClient
    def test_route_returns_created_site_json(
        self, client, mock_db, monkeypatch, site_factory
    ):
        def fake_post_new_site(session, site):
            assert site.nif == "A1234567B"
            assert site.city == "Madrid"
            assert session is mock_db
            return site_factory()

        monkeypatch.setattr(sites_router, "post_new_site", fake_post_new_site)

        response = client.post(
            "/sites",
            json={
                "nif": "A1234567B",
                "city": "Madrid",
                "postal_code": 28013,
                "street": "Gran Via",
                "street_number": None,
                "suite": None,
                "address_info": "Main entrance",
            },
        )

        assert response.status_code == 201
        assert response.json() == {
            "id": 12,
            "nif": "A1234567B",
            "city": "Madrid",
            "postal_code": 28013,
            "street": "Gran Via",
            "street_number": None,
            "suite": None,
            "address_info": "Main entrance",
            "archived_at": None,
            "archive_reason": None,
        }

    def test_route_returns_409_when_site_is_not_created(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_new_site(session, site):
            assert session is mock_db
            raise sites_router.SiteConflictError()

        monkeypatch.setattr(sites_router, "post_new_site", fake_post_new_site)

        response = client.post(
            "/sites",
            json={
                "nif": "A1234567B",
                "city": "Madrid",
                "postal_code": 28013,
                "street": "Gran Via",
                "street_number": None,
                "suite": None,
                "address_info": "Main entrance",
            },
        )

        assert response.status_code == 409
        assert response.json()["detail"].startswith("Site was not added: ")

    def test_route_returns_422_when_site_is_invalid(self, client):
        response = client.post(
            "/sites",
            json={
                "nif": "short",
                "city": "Madrid",
                "postal_code": 28013,
                "street": "Gran Via",
                "street_number": None,
                "suite": None,
                "address_info": "Main entrance",
            },
        )

        assert response.status_code == 422


class TestPostNewSiteRouteUnit:
    def test_returns_created_site(self, monkeypatch, site_factory) -> None:
        fake_session = object()
        site = sites_router.SiteCreate(
            nif="A1234567B",
            city="Madrid",
            postal_code=28013,
            street="Gran Via",
            street_number=None,
            suite=None,
            address_info="Main entrance",
        )
        created_site = site_factory()

        def fake_post_new_site(session, site_info):
            assert site_info is site
            assert session is fake_session
            return created_site

        monkeypatch.setattr(sites_router, "post_new_site", fake_post_new_site)

        result = sites_router.post_new_site_route(
            fake_session,
            _authorized_user=object(),
            site=site,
        )

        assert result == sites_router.SiteOut.model_validate(created_site)

    def test_returns_409_when_site_is_not_created(self, monkeypatch) -> None:
        site = sites_router.SiteCreate(
            nif="A1234567B",
            city="Madrid",
            postal_code=28013,
            street="Gran Via",
            street_number=None,
            suite=None,
            address_info="Main entrance",
        )

        def fake_post_new_site(session, site_info):
            raise sites_router.SiteConflictError()

        monkeypatch.setattr(sites_router, "post_new_site", fake_post_new_site)

        with pytest.raises(HTTPException) as exc_info:
            sites_router.post_new_site_route(
                object(),
                _authorized_user=object(),
                site=site,
            )

        assert exc_info.value.status_code == 409
        assert "Site was not added" in exc_info.value.detail

    def test_returns_404_when_client_does_not_exist(self, monkeypatch) -> None:
        site = sites_router.SiteCreate(
            nif="A1234567B",
            city="Madrid",
            postal_code=28013,
            street="Gran Via",
            street_number=None,
            suite=None,
            address_info="Main entrance",
        )

        def fake_post_new_site(session, site_info):
            raise sites_router.SiteClientNotFoundError()

        monkeypatch.setattr(sites_router, "post_new_site", fake_post_new_site)

        with pytest.raises(HTTPException) as exc_info:
            sites_router.post_new_site_route(
                object(),
                _authorized_user=object(),
                site=site,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Client A1234567B does not exist."

    def test_registers_site_create_response_model_and_created_status(
        self, main_module
    ) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites"
            and "POST" in getattr(route, "methods", set())
        )

        assert route.response_model is sites_router.SiteOut
        assert route.status_code == 201


class TestPostSiteArchivedByIdRouteClient:
    # TestClient
    def test_route_archives_active_site(
        self, client, mock_db, monkeypatch, site_factory, assert_archived_response
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)

        def fake_post_site_archived_by_id(session, site_id, *, archive_request):
            assert session is mock_db
            assert site_id == 12
            assert archive_request.archive_reason == "duplicate"
            return site_factory(archived_at=archived_at, archive_reason="duplicate")

        monkeypatch.setattr(
            sites_router, "post_site_archived_by_id", fake_post_site_archived_by_id
        )

        response = client.post(
            "/sites/12/archive", json={"archive_reason": "duplicate"}
        )

        assert response.status_code == 200
        assert_archived_response(response.json(), "duplicate")

    def test_route_archive_already_archived_site_returns_200(
        self, client, mock_db, monkeypatch, site_factory, assert_archived_response
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)

        def fake_post_site_archived_by_id(session, site_id, *, archive_request):
            assert session is mock_db
            assert site_id == 12
            return site_factory(archived_at=archived_at, archive_reason="old reason")

        monkeypatch.setattr(
            sites_router, "post_site_archived_by_id", fake_post_site_archived_by_id
        )

        response = client.post(
            "/sites/12/archive", json={"archive_reason": "old reason"}
        )

        assert response.status_code == 200
        assert_archived_response(response.json())

    def test_route_returns_404_when_site_does_not_exist(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_site_archived_by_id(session, site_id, *, archive_request):
            assert session is mock_db
            assert site_id == 12
            return None

        monkeypatch.setattr(
            sites_router, "post_site_archived_by_id", fake_post_site_archived_by_id
        )

        response = client.post("/sites/12/archive")

        assert response.status_code == 404
        assert response.json() == {"detail": "Site does not exist: 12."}

    def test_route_returns_422_when_site_id_is_invalid(self, client):
        response = client.post("/sites/not-an-id/archive")

        assert response.status_code == 422


class TestPostSiteArchivedByIdRouteUnit:

    def test_defaults_missing_archive_request(self, monkeypatch) -> None:
        fake_session = object()
        expected = sites_router.SiteOut(
            id=12,
            nif="A1234567B",
            city="Madrid",
            postal_code=28013,
            street="Gran Via",
            street_number=None,
            suite=None,
            address_info="Main entrance",
            archived_at=None,
            archive_reason=None,
        )

        def fake_post_site_archived_by_id(session, site_id, *, archive_request):
            assert session is fake_session
            assert site_id == 12
            assert archive_request == sites_router.ArchiveRequest()
            return expected

        monkeypatch.setattr(
            sites_router,
            "post_site_archived_by_id",
            fake_post_site_archived_by_id,
        )

        result = sites_router.post_site_archived_by_id_route(fake_session, 12)

        assert result == expected

    def test_returns_404_when_site_does_not_exist(self, monkeypatch) -> None:
        def fake_post_site_archived_by_id(session, site_id, *, archive_request):
            return None

        monkeypatch.setattr(
            sites_router,
            "post_site_archived_by_id",
            fake_post_site_archived_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router.post_site_archived_by_id_route(object(), 12)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Site does not exist: 12."


class TestPostSiteRestoredByIdRouteClient:
    # TestClient
    def test_route_restores_archived_site(
        self, client, mock_db, monkeypatch, site_factory, assert_restored_response
    ):
        def fake_post_site_restored_by_id(session, site_id):
            assert session is mock_db
            assert site_id == 12
            return site_factory(archived_at=None, archive_reason=None)

        monkeypatch.setattr(
            sites_router, "post_site_restored_by_id", fake_post_site_restored_by_id
        )

        response = client.post("/sites/12/restore")

        assert response.status_code == 200
        response_json = response.json()
        assert_restored_response(response_json)

    def test_route_restore_active_site_returns_200(
        self, client, mock_db, monkeypatch, site_factory, assert_restored_response
    ):
        def fake_post_site_restored_by_id(session, site_id):
            assert session is mock_db
            assert site_id == 12
            return site_factory(archived_at=None, archive_reason=None)

        monkeypatch.setattr(
            sites_router, "post_site_restored_by_id", fake_post_site_restored_by_id
        )

        response = client.post("/sites/12/restore")

        assert response.status_code == 200
        assert_restored_response(response.json())

    def test_route_returns_404_when_site_does_not_exist(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_site_restored_by_id(session, site_id):
            assert session is mock_db
            assert site_id == 12
            return None

        monkeypatch.setattr(
            sites_router, "post_site_restored_by_id", fake_post_site_restored_by_id
        )

        response = client.post("/sites/12/restore")

        assert response.status_code == 404
        assert response.json() == {"detail": "Site does not exist: 12."}

    def test_route_returns_422_when_site_id_is_invalid(self, client):
        response = client.post("/sites/not-an-id/restore")

        assert response.status_code == 422


class TestPostSiteRestoredByIdRouteUnit:

    def test_returns_restored_site(self, monkeypatch) -> None:
        fake_session = object()
        expected = sites_router.SiteOut(
            id=12,
            nif="A1234567B",
            city="Madrid",
            postal_code=28013,
            street="Gran Via",
            street_number=None,
            suite=None,
            address_info="Main entrance",
            archived_at=None,
            archive_reason=None,
        )

        def fake_post_site_restored_by_id(session, site_id):
            assert session is fake_session
            assert site_id == 12
            return expected

        monkeypatch.setattr(
            sites_router,
            "post_site_restored_by_id",
            fake_post_site_restored_by_id,
        )

        result = sites_router.post_site_restored_by_id_route(fake_session, 12)

        assert result == expected

    def test_returns_404_when_site_does_not_exist(self, monkeypatch) -> None:
        def fake_post_site_restored_by_id(session, site_id):
            return None

        monkeypatch.setattr(
            sites_router,
            "post_site_restored_by_id",
            fake_post_site_restored_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router.post_site_restored_by_id_route(object(), 12)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Site does not exist: 12."


@pytest.mark.usefixtures("admin_user_override")
class TestCreateSiteAnalysisRouteClient:
    def test_route_returns_site_analysis_json_when_found(
        self, main_module, client, mock_db, monkeypatch, site_analysis_factory
    ):
        site_analysis = site_analysis_factory()

        def fake_create_site_analysis(session, site_id):
            assert site_id == 101
            assert session is mock_db
            return site_analysis

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )

        response = client.post("/sites/101/analysis")

        assert response.status_code == 200
        assert response.json()["site_id"] == 101
        assert (
            response.json()["executive_summary"]
            == "Prior inspections show one extinguisher issue."
        )

    def test_route_returns_404_when_site_history_is_not_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_create_site_analysis(session, site_id):
            assert site_id == 999
            assert session is mock_db
            raise HTTPException(status_code=404, detail="Site 999 not found.")

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )

        response = client.post("/sites/999/analysis")

        assert response.status_code == 404
        assert response.json() == {"detail": "Site 999 not found."}

    def test_route_returns_422_when_site_id_is_not_an_int(self, client):
        response = client.post("/sites/not-an-int/analysis")

        assert response.status_code == 422


class TestCreateSiteAnalysisRouteUnit:

    def test_delegates_to_create_site_analysis(
        self, main_module, monkeypatch, site_analysis_factory
    ) -> None:
        fake_session = object()
        site_analysis = site_analysis_factory()

        def fake_create_site_analysis(session, site_id):
            assert site_id == 101
            assert session is fake_session
            return site_analysis

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )

        result = sites_router.create_site_analysis_route(
            fake_session,
            _authorized_user=object(),
            site_id=101,
        )

        assert result == site_analysis

    def test_registers_site_analysis_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/analysis"
        )

        assert route.response_model is sites_router.SiteAnalysis


class TestCreateSiteAnalysis:
    def test_returns_site_analysis_when_history_exists(
        self, main_module, monkeypatch, site_history_factory, site_analysis_factory
    ) -> None:
        fake_session = object()
        site_history = site_history_factory()
        site_analysis = site_analysis_factory()

        def fake_get_site_history(session, site_id, *, include_archived=False):
            assert site_id == 101
            assert session is fake_session
            return site_history

        def fake_summarize_previous_visits(history):
            assert history is site_history
            return site_analysis

        def fake_validate_llm_references(analysis, history):
            assert analysis is site_analysis
            assert history is site_history
            return True

        monkeypatch.setattr(
            sites_router,
            "get_site_history",
            fake_get_site_history,
        )
        monkeypatch.setattr(
            sites_router,
            "summarize_previous_visits",
            fake_summarize_previous_visits,
        )
        monkeypatch.setattr(
            sites_router,
            "validate_llm_references",
            fake_validate_llm_references,
        )

        result = sites_router._create_site_analysis(fake_session, 101)

        assert result == site_analysis

    def test_returns_404_when_site_history_is_not_found(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_site_history(session, site_id, *, include_archived=False):
            return None

        monkeypatch.setattr(
            sites_router,
            "get_site_history",
            fake_get_site_history,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router._create_site_analysis(object(), 999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Site 999 not found."

    @pytest.mark.parametrize(
        "exception_factory",
        [
            lambda main_module: sites_router.APIError(
                "API unavailable",
                request=Request("POST", "https://api.anthropic.com"),
                body=None,
            ),
            lambda main_module: sites_router.ValidationError.from_exception_data(
                "SiteAnalysis",
                [{"type": "missing", "loc": ("site_id",), "input": {}}],
            ),
            lambda main_module: sites_router.JSONDecodeError("Invalid JSON", "{", 0),
        ],
    )
    def test_returns_502_when_ai_analysis_fails(
        self, main_module, monkeypatch, site_history_factory, exception_factory
    ) -> None:
        site_history = site_history_factory()

        def fake_get_site_history(session, site_id, *, include_archived=False):
            return site_history

        def fake_summarize_previous_visits(history):
            raise exception_factory(main_module)

        monkeypatch.setattr(
            sites_router,
            "get_site_history",
            fake_get_site_history,
        )
        monkeypatch.setattr(
            sites_router,
            "summarize_previous_visits",
            fake_summarize_previous_visits,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router._create_site_analysis(object(), 101)

        assert exc_info.value.status_code == 502
        assert exc_info.value.detail == "AI analysis failed for site 101."

    def test_returns_502_when_analysis_references_invalid_evidence(
        self, main_module, monkeypatch, site_history_factory, site_analysis_factory
    ) -> None:
        site_history = site_history_factory()
        site_analysis = site_analysis_factory()

        def fake_get_site_history(session, site_id, *, include_archived=False):
            return site_history

        def fake_summarize_previous_visits(history):
            return False, "v-test", site_analysis

        def fake_validate_llm_references(analysis, history):
            return False

        monkeypatch.setattr(
            sites_router,
            "get_site_history",
            fake_get_site_history,
        )
        monkeypatch.setattr(
            sites_router,
            "summarize_previous_visits",
            fake_summarize_previous_visits,
        )
        monkeypatch.setattr(
            sites_router,
            "validate_llm_references",
            fake_validate_llm_references,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router._create_site_analysis(object(), 101)

        assert exc_info.value.status_code == 502
        assert (
            exc_info.value.detail == "LLM model returned invalid evidence for site 101."
        )


@pytest.mark.usefixtures("viewer_user_override")
class TestGetSiteAttachmentsRouteClient:
    def test_route_returns_site_attachments_json_when_found(
        self, main_module, client, mock_db, monkeypatch, id_record_factory
    ):
        site_attachments = sites_router.SiteAttachmentsOut(
            site_id=12,
            attachments=[],
        )

        def fake_get_site_attachments(session, site_id, *, include_archived=False):
            assert site_id == 12
            assert session is mock_db
            return site_attachments

        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        response = client.get("/sites/12/attachments")

        assert response.status_code == 200
        assert response.json() == {"site_id": 12, "attachments": []}

    def test_route_returns_empty_attachment_list_when_site_has_none(
        self, main_module, client, mock_db, monkeypatch, id_record_factory
    ):
        def fake_get_site_attachments(session, site_id, *, include_archived=False):
            assert site_id == 999
            assert session is mock_db
            return None

        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        response = client.get("/sites/999/attachments")

        assert response.status_code == 200
        assert response.json() == {"site_id": 999, "attachments": []}

    def test_route_returns_404_when_site_is_not_found(
        self, client, mock_db, monkeypatch
    ):
        def fake_get_site_attachments(session, site_id, *, include_archived=False):
            assert site_id == 999
            assert session is mock_db
            raise sites_router.SiteNotFoundError()

        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        response = client.get("/sites/999/attachments")

        assert response.status_code == 404
        assert response.json() == {"detail": "No site for this id found: 999."}

    def test_route_returns_404_when_client_is_not_found(
        self, client, mock_db, monkeypatch
    ):
        def fake_get_site_attachments(session, site_id, *, include_archived=False):
            assert site_id == 999
            assert session is mock_db
            raise sites_router.SiteClientNotFoundError()

        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        response = client.get("/sites/999/attachments")

        assert response.status_code == 404
        assert response.json() == {"detail": "No client for this site found: 999."}

    def test_route_returns_422_when_site_id_is_not_an_int(self, client):
        response = client.get("/sites/not-an-int/attachments")

        assert response.status_code == 422


class TestGetSiteAttachmentsRouteUnit:

    def test_returns_site_attachments_when_found(
        self, main_module, monkeypatch
    ) -> None:
        fake_session = object()
        site_attachments = sites_router.SiteAttachmentsOut(
            site_id=12,
            attachments=[],
        )

        def fake_get_site_attachments(session, site_id, *, include_archived=False):
            assert site_id == 12
            assert session is fake_session
            return site_attachments

        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        result = sites_router.get_site_attachments_route(
            fake_session,
            _authorized_user=object(),
            site_id=12,
        )

        assert result == site_attachments

    def test_returns_empty_attachment_list_when_site_has_none(
        self, monkeypatch
    ) -> None:
        def fake_get_site_attachments(session, site_id, *, include_archived=False):
            return None

        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        result = sites_router.get_site_attachments_route(
            object(),
            _authorized_user=object(),
            site_id=999,
        )

        assert result == sites_router.SiteAttachmentsOut(site_id=999, attachments=[])

    def test_returns_404_when_site_is_not_found(self, monkeypatch) -> None:
        def fake_get_site_attachments(session, site_info, *, include_archived):
            raise sites_router.SiteNotFoundError()

        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router.get_site_attachments_route(
                object(),
                _authorized_user=object(),
                site_id=999,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No site for this id found: 999."

    def test_returns_404_when_client_is_not_found(self, monkeypatch) -> None:
        def fake_get_site_attachments(session, site_info, *, include_archived):
            raise sites_router.SiteClientNotFoundError()

        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router.get_site_attachments_route(
                object(),
                _authorized_user=object(),
                site_id=999,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No client for this site found: 999."

    def test_registers_site_attachments_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/attachments"
        )

        assert route.response_model is sites_router.SiteAttachmentsOut
