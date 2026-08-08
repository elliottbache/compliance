from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from compliance.api.routers import audit_events as audit_events_router
from compliance.db.models import AuditAction, AuditTargetType
from fastapi import HTTPException


def _audit_event(**overrides):
    event = SimpleNamespace(
        id=1,
        actor_user_id=10,
        actor_email="alice@example.com",
        action=AuditAction.FINDING_CREATED,
        target_type=AuditTargetType.FINDING,
        target_id="42",
        created_at=datetime(2026, 8, 7, 10, 0, tzinfo=UTC),
        context={"finding_id": 42},
    )
    event.__dict__.update(overrides)
    return event


@pytest.mark.usefixtures("admin_user_override")
class TestGetAuditEventsRouteClient:
    # TestClient
    def test_route_returns_audit_events_json(self, client, mock_db, monkeypatch):
        def fake_get_audit_events(
            session,
            *,
            actor_user_id,
            actor_email,
            action,
            target_type,
            target_id,
            created_from,
            created_to,
            limit,
            offset,
        ):
            assert session is mock_db
            assert actor_user_id == 10
            assert actor_email == "alice@example.com"
            assert action == AuditAction.FINDING_CREATED
            assert target_type == AuditTargetType.FINDING
            assert target_id == "42"
            assert created_from == datetime(2026, 8, 1, 0, 0, tzinfo=UTC)
            assert created_to == datetime(2026, 8, 7, 23, 59, 59, tzinfo=UTC)
            assert limit == 50
            assert offset == 5
            return [_audit_event()]

        monkeypatch.setattr(
            audit_events_router, "get_audit_events", fake_get_audit_events
        )

        response = client.get(
            "/audit-events"
            "?actor_user_id=10"
            "&actor_email=alice@example.com"
            "&action=finding.created"
            "&target_type=finding"
            "&target_id=42"
            "&created_from=2026-08-01T00:00:00Z"
            "&created_to=2026-08-07T23:59:59Z"
            "&limit=50"
            "&offset=5"
        )

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": 1,
                "actor_user_id": 10,
                "actor_email": "alice@example.com",
                "action": "finding.created",
                "target_type": "finding",
                "target_id": "42",
                "created_at": "2026-08-07T10:00:00Z",
                "context": {"finding_id": 42},
            }
        ]


@pytest.mark.usefixtures("viewer_user_override")
class TestGetAuditEventsRouteAccessClient:
    # TestClient
    def test_route_rejects_non_admin_user(self, client):
        response = client.get("/audit-events")

        assert response.status_code == 403


class TestGetAuditEventsRouteUnit:
    def test_returns_audit_events(self, monkeypatch) -> None:
        fake_session = object()
        created_from = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)
        created_to = datetime(2026, 8, 7, 23, 59, 59, tzinfo=UTC)
        audit_events = [_audit_event()]
        expected = [
            audit_events_router.AuditEventOut.model_validate(audit_event)
            for audit_event in audit_events
        ]

        def fake_get_audit_events(
            session,
            *,
            actor_user_id,
            actor_email,
            action,
            target_type,
            target_id,
            created_from,
            created_to,
            limit,
            offset,
        ):
            assert session is fake_session
            assert actor_user_id == 10
            assert actor_email == "alice@example.com"
            assert action == AuditAction.FINDING_CREATED
            assert target_type == AuditTargetType.FINDING
            assert target_id == "42"
            assert created_from == created_from_filter
            assert created_to == created_to_filter
            assert limit == 50
            assert offset == 5
            return audit_events

        created_from_filter = created_from
        created_to_filter = created_to
        monkeypatch.setattr(
            audit_events_router, "get_audit_events", fake_get_audit_events
        )

        result = audit_events_router.get_audit_events_route(
            fake_session,
            _authorized_user=object(),
            actor_user_id=10,
            actor_email="alice@example.com",
            action=AuditAction.FINDING_CREATED,
            target_type=AuditTargetType.FINDING,
            target_id="42",
            created_from=created_from,
            created_to=created_to,
            limit=50,
            offset=5,
        )

        assert result == expected

    def test_raises_422_when_created_from_is_after_created_to(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            audit_events_router.get_audit_events_route(
                object(),
                _authorized_user=object(),
                created_from=datetime(2026, 8, 8, 0, 0, tzinfo=UTC),
                created_to=datetime(2026, 8, 7, 0, 0, tzinfo=UTC),
            )

        assert exc_info.value.status_code == 422
        assert "created_from" in exc_info.value.detail

    def test_registers_audit_events_list_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.flat_routes
            if getattr(route, "path", None) == "/audit-events"
            and "GET" in getattr(route, "methods", set())
        )

        assert route.response_model == list[audit_events_router.AuditEventOut]

    def test_registers_admin_dependency(self, main_module) -> None:
        route = next(
            route
            for route in main_module.flat_routes
            if getattr(route, "path", None) == "/audit-events"
            and "GET" in getattr(route, "methods", set())
        )

        dependency_names = {
            dependency.call.__name__
            for dependency in route.dependant.dependencies
            if dependency.call is not None
        }
        assert "dependency" in dependency_names
