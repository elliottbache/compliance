import pytest
from fastapi import HTTPException

from compliance.api.routers import regulations as regulations_router


class TestGetRegulationsRoute:
    def test_client_returns_regulations_json(
        self, client, mock_db, monkeypatch, regulation_record_factory
    ):
        def fake_get_regulations(
            session, *, certifier_id, limit, offset, include_archived=False
        ):
            assert session is mock_db
            assert certifier_id == 7
            assert limit == 2
            assert offset == 1
            return [
                regulations_router.RegulationOut.model_validate(
                    regulation_record_factory()
                ),
                regulations_router.RegulationOut.model_validate(
                    regulation_record_factory(
                        id=4,
                        title="Electrical Safety 2026",
                    )
                ),
            ]

        monkeypatch.setattr(regulations_router, "get_regulations", fake_get_regulations)

        response = client.get("/regulations?certifier_id=7&limit=2&offset=1")

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": 3,
                "title": "Fire Safety 2026",
                "description": "Fire safety requirements for commercial sites.",
                "published_date": "2026-01-15",
            },
            {
                "id": 4,
                "title": "Electrical Safety 2026",
                "description": "Fire safety requirements for commercial sites.",
                "published_date": "2026-01-15",
            },
        ]

    def test_client_returns_422_when_limit_is_invalid(self, client):
        response = client.get("/regulations?limit=0")

        assert response.status_code == 422

    def test_returns_regulations(self, monkeypatch, regulation_record_factory) -> None:
        fake_session = object()
        expected_regulations = [
            regulations_router.RegulationOut.model_validate(
                regulation_record_factory()
            ),
        ]

        def fake_get_regulations(
            session, *, certifier_id, limit, offset, include_archived=False
        ):
            assert session is fake_session
            assert certifier_id == 7
            assert limit == 10
            assert offset == 5
            return expected_regulations

        monkeypatch.setattr(regulations_router, "get_regulations", fake_get_regulations)

        result = regulations_router.get_regulations_route(
            fake_session, certifier_id=7, limit=10, offset=5
        )

        assert result == expected_regulations

    def test_returns_404_when_certifier_filter_does_not_exist(
        self, monkeypatch
    ) -> None:
        def fake_get_regulations(
            session, *, certifier_id, limit, offset, include_archived=False
        ):
            assert certifier_id == 999
            return None

        monkeypatch.setattr(regulations_router, "get_regulations", fake_get_regulations)

        with pytest.raises(HTTPException) as exc_info:
            regulations_router.get_regulations_route(
                object(), certifier_id=999, limit=None, offset=0
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Certifier does not exist: 999"

    def test_registers_regulation_list_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/regulations"
            and "GET" in getattr(route, "methods", set())
        )

        assert route.response_model == list[regulations_router.RegulationOut]


class TestGetRegulationByIdRoute:
    def test_client_returns_regulation_json_when_found(
        self, client, mock_db, monkeypatch, regulation_record_factory
    ):
        def fake_get_regulation_by_id(
            regulation_id, session, *, include_archived=False
        ):
            assert regulation_id == 3
            assert session is mock_db
            return regulation_record_factory()

        monkeypatch.setattr(
            regulations_router, "get_regulation_by_id", fake_get_regulation_by_id
        )

        response = client.get("/regulations/3")

        assert response.status_code == 200
        assert response.json() == {
            "id": 3,
            "title": "Fire Safety 2026",
            "description": "Fire safety requirements for commercial sites.",
            "published_date": "2026-01-15",
        }

    def test_client_returns_404_when_regulation_is_not_found(
        self, client, mock_db, monkeypatch
    ):
        def fake_get_regulation_by_id(
            regulation_id, session, *, include_archived=False
        ):
            assert regulation_id == 999
            assert session is mock_db
            return None

        monkeypatch.setattr(
            regulations_router, "get_regulation_by_id", fake_get_regulation_by_id
        )

        response = client.get("/regulations/999")

        assert response.status_code == 404
        assert response.json() == {"detail": "No regulation for this id found: 999"}

    def test_client_returns_422_when_regulation_id_is_not_an_int(self, client):
        response = client.get("/regulations/not-an-int")

        assert response.status_code == 422

    def test_returns_regulation_when_found(
        self, monkeypatch, regulation_record_factory
    ) -> None:
        fake_session = object()
        regulation = regulation_record_factory()

        def fake_get_regulation_by_id(
            regulation_id, session, *, include_archived=False
        ):
            assert regulation_id == 3
            assert session is fake_session
            return regulation

        monkeypatch.setattr(
            regulations_router, "get_regulation_by_id", fake_get_regulation_by_id
        )

        result = regulations_router.get_regulation_by_id_route(3, fake_session)

        assert result == regulations_router.RegulationOut.model_validate(regulation)

    def test_returns_404_when_regulation_is_not_found(self, monkeypatch) -> None:
        def fake_get_regulation_by_id(
            regulation_id, session, *, include_archived=False
        ):
            return None

        monkeypatch.setattr(
            regulations_router, "get_regulation_by_id", fake_get_regulation_by_id
        )

        with pytest.raises(HTTPException) as exc_info:
            regulations_router.get_regulation_by_id_route(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No regulation for this id found: 999"

    def test_registers_regulation_output_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/regulations/{regulation_id}"
        )

        assert route.response_model is regulations_router.RegulationOut


class TestPostNewRegulationRoute:
    def test_client_returns_created_regulation_json(
        self, client, mock_db, monkeypatch, regulation_record_factory
    ):
        created_regulation = regulation_record_factory()

        def fake_post_new_regulation(regulation, session):
            assert regulation.title == "Fire Safety 2026"
            assert session is mock_db
            return created_regulation

        monkeypatch.setattr(
            regulations_router, "post_new_regulation", fake_post_new_regulation
        )

        response = client.post(
            "/regulations",
            json={
                "title": "Fire Safety 2026",
                "description": "Fire safety requirements for commercial sites.",
                "published_date": "2026-01-15",
            },
        )

        assert response.status_code == 201
        assert response.json() == {
            "id": 3,
            "title": "Fire Safety 2026",
            "description": "Fire safety requirements for commercial sites.",
            "published_date": "2026-01-15",
        }

    def test_client_returns_409_when_regulation_conflicts(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_new_regulation(regulation, session):
            assert session is mock_db
            raise regulations_router.RegulationConflictError()

        monkeypatch.setattr(
            regulations_router, "post_new_regulation", fake_post_new_regulation
        )

        response = client.post(
            "/regulations",
            json={
                "title": "Fire Safety 2026",
                "description": "Fire safety requirements for commercial sites.",
                "published_date": "2026-01-15",
            },
        )

        assert response.status_code == 409
        assert response.json()["detail"].startswith("Regulation was not added: ")

    def test_client_returns_422_when_title_is_too_long(self, client):
        response = client.post(
            "/regulations",
            json={
                "title": "x" * 81,
                "description": "Fire safety requirements for commercial sites.",
                "published_date": "2026-01-15",
            },
        )

        assert response.status_code == 422

    def test_returns_created_regulation(
        self, monkeypatch, regulation_record_factory
    ) -> None:
        fake_session = object()
        regulation = regulations_router.RegulationCreate(
            title="Fire Safety 2026",
            description="Fire safety requirements for commercial sites.",
            published_date="2026-01-15",
        )
        created_regulation = regulation_record_factory()

        def fake_post_new_regulation(regulation_info, session):
            assert regulation_info is regulation
            assert session is fake_session
            return created_regulation

        monkeypatch.setattr(
            regulations_router, "post_new_regulation", fake_post_new_regulation
        )

        result = regulations_router.post_new_regulation_route(regulation, fake_session)

        assert result == regulations_router.RegulationOut.model_validate(
            created_regulation
        )

    def test_returns_409_when_regulation_title_already_exists(
        self, monkeypatch
    ) -> None:
        regulation = regulations_router.RegulationCreate(
            title="Fire Safety 2026",
            description="Fire safety requirements for commercial sites.",
            published_date="2026-01-15",
        )

        def fake_post_new_regulation(regulation_info, session):
            raise regulations_router.RegulationTitleConflictError()

        monkeypatch.setattr(
            regulations_router, "post_new_regulation", fake_post_new_regulation
        )

        with pytest.raises(HTTPException) as exc_info:
            regulations_router.post_new_regulation_route(regulation, object())

        assert exc_info.value.status_code == 409
        assert (
            exc_info.value.detail
            == "Regulation with title Fire Safety 2026 already exists."
        )

    def test_returns_409_when_regulation_conflicts(self, monkeypatch) -> None:
        regulation = regulations_router.RegulationCreate(
            title="Fire Safety 2026",
            description="Fire safety requirements for commercial sites.",
            published_date="2026-01-15",
        )

        def fake_post_new_regulation(regulation_info, session):
            raise regulations_router.RegulationConflictError()

        monkeypatch.setattr(
            regulations_router, "post_new_regulation", fake_post_new_regulation
        )

        with pytest.raises(HTTPException) as exc_info:
            regulations_router.post_new_regulation_route(regulation, object())

        assert exc_info.value.status_code == 409
        assert "Regulation was not added" in exc_info.value.detail

    def test_registers_regulation_create_response_model_and_created_status(
        self, main_module
    ) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/regulations"
            and "POST" in getattr(route, "methods", set())
        )

        assert route.response_model is regulations_router.RegulationOut
        assert route.status_code == 201
