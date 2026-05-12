from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from httpx import Request

from compliance.api.routers import sites as sites_router


class TestGetSitesRoute:
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

    # unittests
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
            fake_session, nif="A1234567B", limit=10, offset=5
        )

        assert result == expected_sites

    def test_returns_404_when_client_filter_does_not_exist(self, monkeypatch) -> None:
        def fake_get_sites(session, *, nif, limit, offset, include_archived=False):
            assert nif == "A1234567B"
            return None

        monkeypatch.setattr(sites_router, "get_sites", fake_get_sites)

        with pytest.raises(HTTPException) as exc_info:
            sites_router.get_sites_route(
                object(), nif="A1234567B", limit=None, offset=0
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


class TestGetSiteByIdRoute:
    # TestClient
    def test_route_returns_site_json_when_found(
        self, main_module, client, mock_db, monkeypatch, site_factory
    ):
        def fake_get_site_by_id(session, site_id, *, include_archived=False):
            assert site_id == 12
            assert session is mock_db
            return site_factory()

        monkeypatch.setattr(sites_router, "get_site_by_id", fake_get_site_by_id)

        response = client.get("/sites/12")

        assert response.status_code == 200
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

    def test_route_returns_404_when_site_is_not_found(
        self, main_module, client, mock_db, monkeypatch
    ):

        def fake_get_site_by_id(session, site_id, *, include_archived=False):
            assert site_id == 999
            assert session is mock_db
            raise sites_router.SiteNotFoundError()

        monkeypatch.setattr(sites_router, "get_site_by_id", fake_get_site_by_id)

        response = client.get("/sites/999")

        assert response.status_code == 404
        assert response.json() == {"detail": "No site for this id found: 999."}

    def test_route_returns_422_when_site_id_is_not_an_int(
        self, main_module, client, mock_db, monkeypatch, site_factory
    ):
        def fake_get_site_by_id(session, site_id, *, include_archived=False):
            assert site_id == 12
            assert session is mock_db
            return site_factory()

        monkeypatch.setattr(sites_router, "get_site_by_id", fake_get_site_by_id)

        response = client.get("/sites/not-an-int")

        assert response.status_code == 422

    # unittests
    def test_returns_site_when_found(self, main_module, monkeypatch) -> None:
        fake_session = object()
        site = SimpleNamespace(
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

        def fake_get_site_by_id(session, site_id, *, include_archived=False):
            assert site_id == 12
            assert session is fake_session
            return site

        monkeypatch.setattr(sites_router, "get_site_by_id", fake_get_site_by_id)

        result = sites_router.get_site_by_id_route(fake_session, 12)

        assert result == sites_router.SiteOut.model_validate(site)

    def test_returns_404_when_site_is_not_found(self, monkeypatch) -> None:
        def fake_get_site_by_id(session, site_id, *, include_archived=False):
            assert site_id == 999
            raise sites_router.SiteNotFoundError()

        monkeypatch.setattr(sites_router, "get_site_by_id", fake_get_site_by_id)

        with pytest.raises(HTTPException) as exc_info:
            sites_router.get_site_by_id_route(object(), 999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No site for this id found: 999."

    def test_registers_site_output_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}"
        )

        assert route.response_model is sites_router.SiteOut


class TestGetSiteCertificationsRoute:
    # TestClient
    def test_route_returns_certifications_json_when_found(
        self, main_module, client, mock_db, monkeypatch, certifications_factory
    ):
        def fake_get_site_by_id(session, site_id, *, include_archived=False):
            assert site_id == 12
            assert session is mock_db
            assert include_archived is True
            return SimpleNamespace(id=site_id)

        def fake_get_site_certifications(
            session, site_id, *, limit, offset, include_archived=False
        ):
            assert site_id == 12
            assert session is mock_db
            assert include_archived is True
            return certifications_factory(2)

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            fake_get_site_by_id,
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_certifications",
            fake_get_site_certifications,
        )

        response = client.get("/sites/12/certifications?include_archived=true")

        assert response.status_code == 200
        assert response.json() == {
            "site_id": 12,
            "certifications": [
                {
                    "id": 100,
                    "certifier_id": 200,
                    "regulation_id": 300,
                    "site_id": 12,
                    "result": "Pass",
                    "inspection_date": "2023-10-15",
                    "resolution_date": "2023-10-20",
                    "archived_at": None,
                    "archive_reason": None,
                },
                {
                    "id": 101,
                    "certifier_id": 200,
                    "regulation_id": 300,
                    "site_id": 12,
                    "result": "Pass",
                    "inspection_date": "2023-10-15",
                    "resolution_date": "2023-10-20",
                    "archived_at": None,
                    "archive_reason": None,
                },
            ],
        }

    def test_route_returns_empty_list_when_site_has_no_certifications(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_site_by_id(session, site_id, *, include_archived=False):
            assert site_id == 999
            assert session is mock_db
            return SimpleNamespace(id=site_id)

        def fake_get_site_certifications(
            session, site_id, *, limit, offset, include_archived=False
        ):
            assert site_id == 999
            assert session is mock_db
            return []

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            fake_get_site_by_id,
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_certifications",
            fake_get_site_certifications,
        )

        response = client.get("/sites/999/certifications")

        assert response.status_code == 200
        assert response.json() == {"site_id": 999, "certifications": []}

    def test_route_returns_404_when_site_is_not_found(
        self, client, mock_db, monkeypatch
    ):
        def fake_get_site_certifications(session, site_id, **kwargs):
            assert site_id == 999
            assert session is mock_db
            raise sites_router.SiteNotFoundError()

        monkeypatch.setattr(
            sites_router,
            "get_site_certifications",
            fake_get_site_certifications,
        )

        response = client.get("/sites/999/certifications")

        assert response.status_code == 404
        assert response.json() == {"detail": "No site for this id found: 999."}

    def test_route_returns_422_when_site_id_is_not_an_int(self, client):
        response = client.get("/sites/not-an-int/certifications")

        assert response.status_code == 422

    # unittests
    def test_returns_certifications_for_site(self, main_module, monkeypatch) -> None:
        fake_session = object()
        certifications = [
            SimpleNamespace(
                id=42,
                certifier_id=7,
                regulation_id=3,
                site_id=12,
                result="Pass",
                inspection_date=date(2026, 4, 1),
                resolution_date=date(2026, 4, 15),
                archived_at=None,
                archive_reason=None,
            ),
            SimpleNamespace(
                id=43,
                certifier_id=8,
                regulation_id=3,
                site_id=12,
                result="Fail",
                inspection_date=date(2026, 5, 1),
                resolution_date=None,
                archived_at=None,
                archive_reason=None,
            ),
        ]

        def fake_get_site_certifications(
            session, site_id, *, limit, offset, include_archived=False
        ):
            assert site_id == 12
            assert session is fake_session
            assert limit is None
            assert offset == 0
            return certifications

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            lambda session, site_id, *, include_archived=False: SimpleNamespace(
                id=site_id
            ),
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_certifications",
            fake_get_site_certifications,
        )

        result = sites_router.get_site_certifications_route(fake_session, 12)

        assert result == sites_router.SiteCertificationsOut.model_validate(
            {"site_id": 12, "certifications": certifications}
        )

    def test_passes_limit_and_offset_to_service(self, main_module, monkeypatch) -> None:
        fake_session = object()

        def fake_get_site_certifications(
            session, site_id, *, limit, offset, include_archived=False
        ):
            assert site_id == 12
            assert session is fake_session
            assert limit == 10
            assert offset == 20
            return []

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            lambda session, site_id, *, include_archived=False: SimpleNamespace(
                id=site_id
            ),
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_certifications",
            fake_get_site_certifications,
        )

        result = sites_router.get_site_certifications_route(
            fake_session, 12, limit=10, offset=20
        )

        assert result == sites_router.SiteCertificationsOut(
            site_id=12, certifications=[]
        )

    def test_returns_empty_list_when_site_has_no_certifications(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_site_certifications(
            site_id, session, *, limit, offset, include_archived=False
        ):
            return []

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            lambda site_id, session, *, include_archived=False: SimpleNamespace(
                id=site_id
            ),
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_certifications",
            fake_get_site_certifications,
        )

        result = sites_router.get_site_certifications_route(object(), 999)

        assert result == sites_router.SiteCertificationsOut(
            site_id=999, certifications=[]
        )

    def test_returns_404_when_site_is_not_found(self, monkeypatch) -> None:
        def fake_get_site_certifications(session, site_id, **kwargs):
            assert site_id == 999
            raise sites_router.SiteNotFoundError()

        monkeypatch.setattr(
            sites_router,
            "get_site_certifications",
            fake_get_site_certifications,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router.get_site_certifications_route(object(), 999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No site for this id found: 999."

    def test_returns_404_when_site_is_archived_by_default(self, monkeypatch) -> None:
        def fake_get_site_certifications(
            session, site_id, *, limit, offset, include_archived=False
        ):
            assert site_id == 12
            assert include_archived is False
            raise sites_router.SiteNotFoundError()

        monkeypatch.setattr(
            sites_router,
            "get_site_certifications",
            fake_get_site_certifications,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router.get_site_certifications_route(object(), 12)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No site for this id found: 12."

    def test_registers_certification_list_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/certifications"
        )

        assert route.response_model is sites_router.SiteCertificationsOut


class TestGetSiteHistoryRoute:
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

    # unittests
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

        result = sites_router.get_site_history_route(fake_session, 12)

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
            sites_router.get_site_history_route(object(), 999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No site history found for this id: 999"

    def test_registers_site_history_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/history"
        )

        assert route.response_model is sites_router.SiteHistory


class TestPostNewSiteRoute:
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

    # unittests
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

        result = sites_router.post_new_site_route(fake_session, site)

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
            sites_router.post_new_site_route(object(), site)

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
            sites_router.post_new_site_route(object(), site)

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


class TestPostSiteArchivedByIdRoute:
    # TestClient
    def test_route_archives_active_site(
        self, client, mock_db, monkeypatch, site_factory
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
        assert response.json()["archived_at"] is not None
        assert response.json()["archive_reason"] == "duplicate"

    def test_route_archive_already_archived_site_returns_200(
        self, client, mock_db, monkeypatch, site_factory
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
        assert response.json()["archived_at"] is not None

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


class TestPostSiteRestoredByIdRoute:
    # TestClient
    def test_route_restores_archived_site(
        self, client, mock_db, monkeypatch, site_factory
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
        assert response_json["archived_at"] is None
        assert response_json["archive_reason"] is None

    def test_route_restore_active_site_returns_200(
        self, client, mock_db, monkeypatch, site_factory
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
        assert response.json()["archived_at"] is None

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


class TestCreateSiteAnalysisRoute:
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

        result = sites_router.create_site_analysis_route(fake_session, 101)

        assert result == site_analysis

    def test_registers_site_analysis_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/analysis"
        )

        assert route.response_model is sites_router.SiteAnalysis


class TestAnalyzeSiteReturnMarkdownRoute:
    def test_route_returns_rendered_markdown(
        self, main_module, client, mock_db, monkeypatch, site_analysis_factory
    ):
        site_analysis = site_analysis_factory()

        def fake_create_site_analysis(session, site_id):
            assert site_id == 101
            assert session is mock_db
            return site_analysis

        def fake_build_site_analysis_markdown(analysis):
            assert analysis is site_analysis
            return "# Site Analysis\nMarkdown body."

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )
        monkeypatch.setattr(
            sites_router,
            "build_site_analysis_markdown",
            fake_build_site_analysis_markdown,
        )

        response = client.post("/sites/101/analysis/markdown")

        assert response.status_code == 200
        assert response.text == "# Site Analysis\nMarkdown body."
        assert response.headers["content-type"].startswith("text/markdown")

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

        response = client.post("/sites/999/analysis/markdown")

        assert response.status_code == 404
        assert response.json() == {"detail": "Site 999 not found."}

    def test_route_returns_422_when_site_id_is_not_an_int(self, client):
        response = client.post("/sites/not-an-int/analysis/markdown")

        assert response.status_code == 422

    def test_returns_rendered_markdown(
        self, main_module, monkeypatch, site_analysis_factory
    ) -> None:
        fake_session = object()
        site_analysis = site_analysis_factory()

        def fake_create_site_analysis(session, site_id):
            assert site_id == 101
            assert session is fake_session
            return site_analysis

        def fake_build_site_analysis_markdown(analysis):
            assert analysis is site_analysis
            return "# Site Analysis\nMarkdown body."

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )
        monkeypatch.setattr(
            sites_router,
            "build_site_analysis_markdown",
            fake_build_site_analysis_markdown,
        )

        result = sites_router.create_site_analysis_markdown_route(fake_session, 101)

        assert result.body == b"# Site Analysis\nMarkdown body."
        assert result.media_type == "text/markdown"

    def test_does_not_register_markdown_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/analysis/markdown"
        )

        assert route.response_model is None


class TestCreateSiteAnalysisMarkdownDownloadRoute:
    def test_route_returns_rendered_markdown_attachment(
        self, main_module, client, mock_db, monkeypatch, site_analysis_factory
    ):
        site_analysis = site_analysis_factory()

        def fake_create_site_analysis(session, site_id):
            assert site_id == 101
            assert session is mock_db
            return site_analysis

        def fake_build_site_analysis_markdown(analysis):
            assert analysis is site_analysis
            return "# Site Analysis\nMarkdown body."

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )
        monkeypatch.setattr(
            sites_router,
            "build_site_analysis_markdown",
            fake_build_site_analysis_markdown,
        )

        response = client.post("/sites/101/analysis/markdown/download")

        assert response.status_code == 200
        assert response.text == "# Site Analysis\nMarkdown body."
        assert response.headers["content-type"].startswith("text/markdown")
        assert (
            response.headers["content-disposition"]
            == 'attachment; filename="site-101-analysis.md"'
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

        response = client.post("/sites/999/analysis/markdown/download")

        assert response.status_code == 404
        assert response.json() == {"detail": "Site 999 not found."}

    def test_route_returns_422_when_site_id_is_not_an_int(self, client):
        response = client.post("/sites/not-an-int/analysis/markdown/download")

        assert response.status_code == 422

    def test_returns_rendered_markdown_attachment(
        self, main_module, monkeypatch, site_analysis_factory
    ) -> None:
        fake_session = object()
        site_analysis = site_analysis_factory()

        def fake_create_site_analysis(session, site_id):
            assert site_id == 101
            assert session is fake_session
            return site_analysis

        def fake_build_site_analysis_markdown(analysis):
            assert analysis is site_analysis
            return "# Site Analysis\nMarkdown body."

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )
        monkeypatch.setattr(
            sites_router,
            "build_site_analysis_markdown",
            fake_build_site_analysis_markdown,
        )

        result = sites_router.create_site_analysis_markdown_download_route(
            fake_session, 101
        )

        assert result.body == b"# Site Analysis\nMarkdown body."
        assert result.media_type == "text/markdown"
        assert (
            result.headers["content-disposition"]
            == 'attachment; filename="site-101-analysis.md"'
        )

    def test_propagates_404_when_site_history_is_not_found(
        self, main_module, monkeypatch
    ) -> None:
        def fake_create_site_analysis(session, site_id):
            assert site_id == 999
            raise HTTPException(status_code=404, detail="Site 999 not found.")

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router.create_site_analysis_markdown_download_route(object(), 999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Site 999 not found."

    def test_does_not_register_download_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None)
            == "/sites/{site_id}/analysis/markdown/download"
        )

        assert route.response_model is None


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


class TestGetSiteAttachmentsRoute:
    def test_route_returns_site_attachments_json_when_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        site_attachments = sites_router.SiteAttachmentsOut(
            site_id=12,
            attachments=[],
        )

        def fake_get_site_by_id(session, site_id, *, include_archived=False):
            assert site_id == 12
            assert session is mock_db
            return SimpleNamespace(id=site_id)

        def fake_get_site_attachments(session, site_id, *, include_archived=False):
            assert site_id == 12
            assert session is mock_db
            return site_attachments

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            fake_get_site_by_id,
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        response = client.get("/sites/12/attachments")

        assert response.status_code == 200
        assert response.json() == {"site_id": 12, "attachments": []}

    def test_route_returns_empty_attachment_list_when_site_has_none(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_site_by_id(session, site_id, *, include_archived=False):
            assert site_id == 999
            assert session is mock_db
            return SimpleNamespace(id=site_id)

        def fake_get_site_attachments(session, site_id, *, include_archived=False):
            assert site_id == 999
            assert session is mock_db
            return None

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            fake_get_site_by_id,
        )
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
            "get_site_by_id",
            lambda session, site_id, *, include_archived=False: SimpleNamespace(
                id=site_id
            ),
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        result = sites_router.get_site_attachments_route(fake_session, 12)

        assert result == site_attachments

    def test_returns_empty_attachment_list_when_site_has_none(
        self, monkeypatch
    ) -> None:
        def fake_get_site_attachments(session, site_id, *, include_archived=False):
            return None

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            lambda session, site_id, *, include_archived=False: SimpleNamespace(
                id=site_id
            ),
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        result = sites_router.get_site_attachments_route(object(), 999)

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
            sites_router.get_site_attachments_route(object(), 999)

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
            sites_router.get_site_attachments_route(object(), 999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No client for this site found: 999."

    def test_registers_site_attachments_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/attachments"
        )

        assert route.response_model is sites_router.SiteAttachmentsOut
