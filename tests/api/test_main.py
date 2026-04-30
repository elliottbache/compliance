from datetime import date
from importlib import import_module
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


@pytest.fixture
def main_module(monkeypatch):
    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")

    return import_module("compliance.api.main")


class TestGetSiteByIdRoute:
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
        )

        def fake_get_site_by_id(site_id, session):
            assert site_id == 12
            assert session is fake_session
            return site

        monkeypatch.setattr(main_module, "get_site_by_id", fake_get_site_by_id)

        result = main_module.get_site_by_id_route(12, fake_session)

        assert result == main_module.SiteOut.model_validate(site)

    def test_returns_404_when_site_is_not_found(self, main_module, monkeypatch) -> None:
        def fake_get_site_by_id(site_id, session):
            return None

        monkeypatch.setattr(main_module, "get_site_by_id", fake_get_site_by_id)

        with pytest.raises(HTTPException) as exc_info:
            main_module.get_site_by_id_route(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No site for this id found: 999"

    def test_registers_site_output_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}"
        )

        assert route.response_model is main_module.SiteOut


class TestGetCertificationByIdRoute:
    def test_returns_certification_when_found(self, main_module, monkeypatch) -> None:
        fake_session = object()
        certification = SimpleNamespace(
            id=42,
            certifier_id=7,
            regulation_id=3,
            site_id=12,
            result="Pass",
            inspection_date=date(2026, 4, 1),
            resolution_date=None,
        )

        def fake_get_certification_by_id(certification_id, session):
            assert certification_id == 42
            assert session is fake_session
            return certification

        monkeypatch.setattr(
            main_module,
            "get_certification_by_id",
            fake_get_certification_by_id,
        )

        result = main_module.get_certification_by_id_route(42, fake_session)

        assert result == main_module.CertificationOut.model_validate(certification)

    def test_returns_404_when_certification_is_not_found(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_certification_by_id(certification_id, session):
            return None

        monkeypatch.setattr(
            main_module,
            "get_certification_by_id",
            fake_get_certification_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            main_module.get_certification_by_id_route(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No certification for this id found: 999"

    def test_registers_certification_output_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/certifications/{certification_id}"
        )

        assert route.response_model is main_module.CertificationOut


class TestGetSiteHistoryByIdRoute:
    def test_returns_site_history_when_found(self, main_module, monkeypatch) -> None:
        fake_session = object()
        site_history = main_module.SiteHistory(
            site_id=12,
            certifications=[],
            inspection_count=0,
            latest_inspection_date=None,
        )

        def fake_get_site_history_by_id(site_id, session):
            assert site_id == 12
            assert session is fake_session
            return site_history

        monkeypatch.setattr(
            main_module,
            "get_site_history_by_id",
            fake_get_site_history_by_id,
        )

        result = main_module.get_site_history_by_id_route(12, fake_session)

        assert result == site_history

    def test_returns_404_when_site_history_is_not_found(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_site_history_by_id(site_id, session):
            return None

        monkeypatch.setattr(
            main_module,
            "get_site_history_by_id",
            fake_get_site_history_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            main_module.get_site_history_by_id_route(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No site history found for this id: 999"

    def test_registers_site_history_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/history"
        )

        assert route.response_model is main_module.SiteHistory


class TestGetSiteAttachmentsOutByIdRoute:
    def test_returns_site_attachments_when_found(
        self, main_module, monkeypatch
    ) -> None:
        fake_session = object()
        site_attachments = main_module.SiteAttachmentsOut(
            site_id=12,
            attachments=[],
        )

        def fake_get_site_attachments_by_id(site_id, session):
            assert site_id == 12
            assert session is fake_session
            return site_attachments

        monkeypatch.setattr(
            main_module,
            "get_site_attachments_by_id",
            fake_get_site_attachments_by_id,
        )

        result = main_module.get_site_attachments_by_id_route(12, fake_session)

        assert result == site_attachments

    def test_returns_404_when_site_attachments_are_not_found(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_site_attachments_by_id(site_id, session):
            return None

        monkeypatch.setattr(
            main_module,
            "get_site_attachments_by_id",
            fake_get_site_attachments_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            main_module.get_site_attachments_by_id_route(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No attachments found for site 999"

    def test_registers_site_attachments_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/attachments"
        )

        assert route.response_model is main_module.SiteAttachmentsOut


class TestPostNewClientRoute:
    def test_returns_created_client(self, main_module, monkeypatch) -> None:
        fake_session = object()
        client = main_module.ClientInOut(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )

        def fake_post_new_client(client_info, session):
            assert client_info is client
            assert session is fake_session
            return client

        monkeypatch.setattr(main_module, "post_new_client", fake_post_new_client)

        result = main_module.post_new_client_route(client, fake_session)

        assert result == client

    def test_returns_409_when_client_is_not_created(
        self, main_module, monkeypatch
    ) -> None:
        client = main_module.ClientInOut(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )

        def fake_post_new_client(client_info, session):
            return None

        monkeypatch.setattr(main_module, "post_new_client", fake_post_new_client)

        with pytest.raises(HTTPException) as exc_info:
            main_module.post_new_client_route(client, object())

        assert exc_info.value.status_code == 409
        assert "Client was not added" in exc_info.value.detail

    def test_registers_client_response_model_and_created_status(
        self, main_module
    ) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/clients"
        )

        assert route.response_model is main_module.ClientInOut
        assert route.status_code == 201
