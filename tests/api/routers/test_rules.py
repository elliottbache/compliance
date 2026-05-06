import pytest
from fastapi import HTTPException

from compliance.api.routers import rules as rules_router


class TestGetRulesRoute:
    def test_client_returns_rules_json(
        self, client, mock_db, monkeypatch, rule_record_factory
    ):
        def fake_get_rules(session, regulation_id, limit, offset):
            assert session is mock_db
            assert regulation_id == 3
            assert limit == 2
            assert offset == 1
            return [
                rules_router.RuleOut.model_validate(rule_record_factory()),
                rules_router.RuleOut.model_validate(
                    rule_record_factory(
                        id=21,
                        rule_index="FS-102",
                        title="Inspection Records",
                    )
                ),
            ]

        monkeypatch.setattr(rules_router, "get_rules", fake_get_rules)

        response = client.get("/rules?regulation_id=3&limit=2&offset=1")

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": 20,
                "regulation_id": 3,
                "rule_index": "FS-101",
                "title": "Equipment Maintenance",
                "description": "Equipment must be maintained.",
            },
            {
                "id": 21,
                "regulation_id": 3,
                "rule_index": "FS-102",
                "title": "Inspection Records",
                "description": "Equipment must be maintained.",
            },
        ]

    def test_client_returns_422_when_limit_is_invalid(self, client):
        response = client.get("/rules?limit=0")

        assert response.status_code == 422

    def test_returns_rules(self, monkeypatch, rule_record_factory) -> None:
        fake_session = object()
        expected_rules = [
            rules_router.RuleOut.model_validate(rule_record_factory()),
        ]

        def fake_get_rules(session, regulation_id, limit, offset):
            assert session is fake_session
            assert regulation_id == 3
            assert limit == 10
            assert offset == 5
            return expected_rules

        monkeypatch.setattr(rules_router, "get_rules", fake_get_rules)

        result = rules_router.get_rules_route(
            fake_session, regulation_id=3, limit=10, offset=5
        )

        assert result == expected_rules

    def test_returns_404_when_regulation_filter_does_not_exist(
        self, monkeypatch
    ) -> None:
        def fake_get_rules(session, regulation_id, limit, offset):
            assert regulation_id == 999
            return None

        monkeypatch.setattr(rules_router, "get_rules", fake_get_rules)

        with pytest.raises(HTTPException) as exc_info:
            rules_router.get_rules_route(
                object(), regulation_id=999, limit=None, offset=0
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Regulation does not exist: 999"

    def test_registers_rule_list_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/rules"
            and "GET" in getattr(route, "methods", set())
        )

        assert route.response_model == list[rules_router.RuleOut]


class TestGetRuleByIdRoute:
    def test_client_returns_rule_json_when_found(
        self, client, mock_db, monkeypatch, rule_record_factory
    ):
        def fake_get_rule_by_id(rule_id, session):
            assert rule_id == 20
            assert session is mock_db
            return rule_record_factory()

        monkeypatch.setattr(rules_router, "get_rule_by_id", fake_get_rule_by_id)

        response = client.get("/rules/20")

        assert response.status_code == 200
        assert response.json() == {
            "id": 20,
            "regulation_id": 3,
            "rule_index": "FS-101",
            "title": "Equipment Maintenance",
            "description": "Equipment must be maintained.",
        }

    def test_client_returns_404_when_rule_is_not_found(
        self, client, mock_db, monkeypatch
    ):
        def fake_get_rule_by_id(rule_id, session):
            assert rule_id == 999
            assert session is mock_db
            return None

        monkeypatch.setattr(rules_router, "get_rule_by_id", fake_get_rule_by_id)

        response = client.get("/rules/999")

        assert response.status_code == 404
        assert response.json() == {"detail": "No rule for this id found: 999"}

    def test_client_returns_422_when_rule_id_is_not_an_int(self, client):
        response = client.get("/rules/not-an-int")

        assert response.status_code == 422

    def test_returns_rule_when_found(self, monkeypatch, rule_record_factory) -> None:
        fake_session = object()
        rule = rule_record_factory()

        def fake_get_rule_by_id(rule_id, session):
            assert rule_id == 20
            assert session is fake_session
            return rule

        monkeypatch.setattr(rules_router, "get_rule_by_id", fake_get_rule_by_id)

        result = rules_router.get_rule_by_id_route(20, fake_session)

        assert result == rules_router.RuleOut.model_validate(rule)

    def test_returns_404_when_rule_is_not_found(self, monkeypatch) -> None:
        def fake_get_rule_by_id(rule_id, session):
            return None

        monkeypatch.setattr(rules_router, "get_rule_by_id", fake_get_rule_by_id)

        with pytest.raises(HTTPException) as exc_info:
            rules_router.get_rule_by_id_route(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No rule for this id found: 999"

    def test_registers_rule_output_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/rules/{rule_id}"
        )

        assert route.response_model is rules_router.RuleOut


class TestPostNewRuleRoute:
    def test_client_returns_created_rule_json(
        self, client, mock_db, monkeypatch, rule_record_factory
    ):
        created_rule = rule_record_factory()

        def fake_post_new_rule(rule, session):
            assert rule.regulation_id == 3
            assert rule.rule_index == "FS-101"
            assert session is mock_db
            return created_rule

        monkeypatch.setattr(rules_router, "post_new_rule", fake_post_new_rule)

        response = client.post(
            "/rules",
            json={
                "regulation_id": 3,
                "rule_index": "FS-101",
                "title": "Equipment Maintenance",
                "description": "Equipment must be maintained.",
            },
        )

        assert response.status_code == 201
        assert response.json() == {
            "id": 20,
            "regulation_id": 3,
            "rule_index": "FS-101",
            "title": "Equipment Maintenance",
            "description": "Equipment must be maintained.",
        }

    def test_client_returns_409_when_rule_conflicts(self, client, mock_db, monkeypatch):
        def fake_post_new_rule(rule, session):
            assert session is mock_db
            raise rules_router.RuleConflictError()

        monkeypatch.setattr(rules_router, "post_new_rule", fake_post_new_rule)

        response = client.post(
            "/rules",
            json={
                "regulation_id": 3,
                "rule_index": "FS-101",
                "title": "Equipment Maintenance",
                "description": "Equipment must be maintained.",
            },
        )

        assert response.status_code == 409
        assert response.json()["detail"].startswith("Rule was not added: ")

    def test_client_returns_422_when_rule_index_is_too_long(self, client):
        response = client.post(
            "/rules",
            json={
                "regulation_id": 3,
                "rule_index": "TOO-LONG-RULE-INDEX",
                "title": "Equipment Maintenance",
                "description": "Equipment must be maintained.",
            },
        )

        assert response.status_code == 422

    def test_returns_created_rule(self, monkeypatch, rule_record_factory) -> None:
        fake_session = object()
        rule = rules_router.RuleCreate(
            regulation_id=3,
            rule_index="FS-101",
            title="Equipment Maintenance",
            description="Equipment must be maintained.",
        )
        created_rule = rule_record_factory()

        def fake_post_new_rule(rule_info, session):
            assert rule_info is rule
            assert session is fake_session
            return created_rule

        monkeypatch.setattr(rules_router, "post_new_rule", fake_post_new_rule)

        result = rules_router.post_new_rule_route(rule, fake_session)

        assert result == rules_router.RuleOut.model_validate(created_rule)

    def test_returns_404_when_regulation_does_not_exist(self, monkeypatch) -> None:
        rule = rules_router.RuleCreate(
            regulation_id=3,
            rule_index="FS-101",
            title="Equipment Maintenance",
            description="Equipment must be maintained.",
        )

        def fake_post_new_rule(rule_info, session):
            raise rules_router.RuleRegulationNotFoundError()

        monkeypatch.setattr(rules_router, "post_new_rule", fake_post_new_rule)

        with pytest.raises(HTTPException) as exc_info:
            rules_router.post_new_rule_route(rule, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Regulation 3 does not exist."

    def test_returns_409_when_rule_index_already_exists(self, monkeypatch) -> None:
        rule = rules_router.RuleCreate(
            regulation_id=3,
            rule_index="FS-101",
            title="Equipment Maintenance",
            description="Equipment must be maintained.",
        )

        def fake_post_new_rule(rule_info, session):
            raise rules_router.RuleIndexConflictError()

        monkeypatch.setattr(rules_router, "post_new_rule", fake_post_new_rule)

        with pytest.raises(HTTPException) as exc_info:
            rules_router.post_new_rule_route(rule, object())

        assert exc_info.value.status_code == 409
        assert (
            exc_info.value.detail
            == "Rule index FS-101 already exists for regulation 3."
        )

    def test_returns_409_when_rule_conflicts(self, monkeypatch) -> None:
        rule = rules_router.RuleCreate(
            regulation_id=3,
            rule_index="FS-101",
            title="Equipment Maintenance",
            description="Equipment must be maintained.",
        )

        def fake_post_new_rule(rule_info, session):
            raise rules_router.RuleConflictError()

        monkeypatch.setattr(rules_router, "post_new_rule", fake_post_new_rule)

        with pytest.raises(HTTPException) as exc_info:
            rules_router.post_new_rule_route(rule, object())

        assert exc_info.value.status_code == 409
        assert "Rule was not added" in exc_info.value.detail

    def test_registers_rule_create_response_model_and_created_status(
        self, main_module
    ) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/rules"
            and "POST" in getattr(route, "methods", set())
        )

        assert route.response_model is rules_router.RuleOut
        assert route.status_code == 201
