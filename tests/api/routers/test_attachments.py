from datetime import date, datetime

import pytest
from fastapi import HTTPException

from compliance.api.routers import attachments as attachments_router


def attachment_out_factory(**overrides):
    """Build an attachment list response payload for route tests."""
    data = {
        "file_type": "pdf",
        "file_name": "evidence",
        "certification_id": 100,
        "description": "Inspection evidence",
        "finding_ids": [1],
        "id": 50,
        "uploaded_at": datetime(2026, 4, 3, 9, 30),
        "archived_at": None,
        "archive_reason": None,
        "inspection_date": date(2026, 4, 1),
        "regulation_id": 5,
        "regulation_title": "USDA Organic",
    }
    data.update(overrides)
    return attachments_router.AttachmentOut.model_validate(data)


class TestGetAttachmentsRoute:
    def test_client_returns_attachments_json(self, client, mock_db, monkeypatch):
        def fake_get_attachments(
            session,
            site_id,
            certification_id,
            rule_id,
            finding_id,
            include_archived=False,
        ):
            assert session is mock_db
            assert site_id is None
            assert certification_id is None
            assert rule_id is None
            assert finding_id is None
            return [attachment_out_factory()]

        monkeypatch.setattr(
            attachments_router,
            "get_attachments",
            fake_get_attachments,
        )

        response = client.get("/attachments")

        assert response.status_code == 200
        assert response.json() == [
            {
                "file_type": "pdf",
                "file_name": "evidence",
                "certification_id": 100,
                "description": "Inspection evidence",
                "finding_ids": [1],
                "id": 50,
                "uploaded_at": "2026-04-03T09:30:00",
                "inspection_date": "2026-04-01",
                "regulation_id": 5,
                "regulation_title": "USDA Organic",
            }
        ]

    def test_client_passes_query_filters_to_service(self, client, mock_db, monkeypatch):
        def fake_get_attachments(
            session,
            site_id,
            certification_id,
            rule_id,
            finding_id,
            include_archived=False,
        ):
            assert session is mock_db
            assert site_id == 71
            assert certification_id == 100
            assert rule_id == 5
            assert finding_id == 1
            assert include_archived is True
            return []

        monkeypatch.setattr(
            attachments_router,
            "get_attachments",
            fake_get_attachments,
        )

        response = client.get(
            "/attachments?site_id=71&certification_id=100&rule_id=5"
            "&finding_id=1&include_archived=true"
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_client_returns_422_when_filter_type_is_invalid(self, client):
        response = client.get("/attachments?site_id=not-an-int")

        assert response.status_code == 422

    def test_returns_attachments_from_service(self, monkeypatch) -> None:
        fake_session = object()
        expected = [attachment_out_factory()]

        def fake_get_attachments(
            session,
            site_id,
            certification_id,
            rule_id,
            finding_id,
            include_archived=False,
        ):
            assert session is fake_session
            assert site_id == 71
            assert certification_id == 100
            assert rule_id == 5
            assert finding_id == 1
            return expected

        monkeypatch.setattr(
            attachments_router,
            "get_attachments",
            fake_get_attachments,
        )

        result = attachments_router.get_attachments_route(
            fake_session,
            site_id=71,
            certification_id=100,
            rule_id=5,
            finding_id=1,
        )

        assert result == expected

    def test_returns_404_when_site_filter_does_not_exist(self, monkeypatch) -> None:
        def fake_get_attachments(
            session,
            site_id,
            certification_id,
            rule_id,
            finding_id,
            include_archived=False,
        ):
            raise attachments_router.AttachmentSiteNotFoundError(site_id)

        monkeypatch.setattr(
            attachments_router,
            "get_attachments",
            fake_get_attachments,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.get_attachments_route(object(), site_id=999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Missing site 999."

    def test_returns_404_when_certification_filter_does_not_exist(
        self, monkeypatch
    ) -> None:
        def fake_get_attachments(
            session,
            site_id,
            certification_id,
            rule_id,
            finding_id,
            include_archived=False,
        ):
            raise attachments_router.AttachmentCertificationNotFoundError(
                certification_id
            )

        monkeypatch.setattr(
            attachments_router,
            "get_attachments",
            fake_get_attachments,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.get_attachments_route(object(), certification_id=999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Missing certification 999."

    def test_returns_404_when_rule_filter_does_not_exist(self, monkeypatch) -> None:
        def fake_get_attachments(
            session,
            site_id,
            certification_id,
            rule_id,
            finding_id,
            include_archived=False,
        ):
            raise attachments_router.AttachmentRuleNotFoundError(rule_id)

        monkeypatch.setattr(
            attachments_router,
            "get_attachments",
            fake_get_attachments,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.get_attachments_route(object(), rule_id=999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Missing rule 999."

    def test_returns_404_when_finding_filter_does_not_exist(self, monkeypatch) -> None:
        def fake_get_attachments(
            session,
            site_id,
            certification_id,
            rule_id,
            finding_id,
            include_archived=False,
        ):
            raise attachments_router.AttachmentFindingNotFoundError(finding_id)

        monkeypatch.setattr(
            attachments_router,
            "get_attachments",
            fake_get_attachments,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.get_attachments_route(object(), finding_id=999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Missing finding 999."

    def test_registers_attachments_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/attachments"
            and "GET" in getattr(route, "methods", set())
        )

        assert route.response_model == list[attachments_router.AttachmentOut]


class TestGetAttachmentByIdRoute:
    def test_client_returns_attachment_without_findings(
        self, main_module, client, mock_db, monkeypatch, attachment_factory
    ):
        def fake_get_attachment_by_id(attachment_id, session, include_archived=False):
            assert attachment_id == 50
            assert session is mock_db
            return attachment_factory()

        monkeypatch.setattr(
            attachments_router, "get_attachment_by_id", fake_get_attachment_by_id
        )

        response = client.get("/attachments/50")

        assert response.status_code == 200
        assert response.json() == {
            "id": 50,
            "file_type": "pdf",
            "file_path": "dummy/evidence.pdf",
            "description": "Inspection evidence",
            "uploaded_at": "2026-04-03T09:30:00",
            "archived_at": None,
            "archive_reason": None,
            "certification_id": 100,
            "inspection_date": "2026-04-01",
            "regulation_id": 5,
            "regulation_title": "USDA Organic",
            "finding_links": [],
        }

    def test_client_returns_attachment_with_two_findings(
        self, main_module, client, mock_db, monkeypatch, attachment_factory
    ):
        def fake_get_attachment_by_id(attachment_id, session, include_archived=False):
            assert attachment_id == 50
            assert session is mock_db
            return attachment_factory(
                finding_links=[
                    {
                        "finding_id": 1,
                        "finding": "Missing document",
                        "rule_index": "7 CFR 205.201",
                        "rule_title": "Organic plan",
                        "rule_description": "Producer must maintain an organic system plan.",
                    },
                    {
                        "finding_id": 2,
                        "finding": "Incomplete record",
                        "rule_index": "7 CFR 205.202",
                        "rule_title": "Land requirements",
                        "rule_description": "Land must meet organic requirements.",
                    },
                ]
            )

        monkeypatch.setattr(
            attachments_router, "get_attachment_by_id", fake_get_attachment_by_id
        )

        response = client.get("/attachments/50")

        assert response.status_code == 200
        assert [
            finding["finding_id"] for finding in response.json()["finding_links"]
        ] == [
            1,
            2,
        ]

    def test_client_returns_404_when_attachment_is_not_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_attachment_by_id(attachment_id, session, include_archived=False):
            assert attachment_id == 999
            assert session is mock_db
            return None

        monkeypatch.setattr(
            attachments_router, "get_attachment_by_id", fake_get_attachment_by_id
        )

        response = client.get("/attachments/999")

        assert response.status_code == 404
        assert response.json() == {"detail": "Attachment 999 not found."}

    def test_client_returns_422_when_attachment_id_is_not_an_int(self, client):
        response = client.get("/attachments/not-an-int")

        assert response.status_code == 422

    def test_returns_attachment_when_found(
        self, main_module, monkeypatch, attachment_factory
    ) -> None:
        fake_session = object()

        def fake_get_attachment_by_id(attachment_id, session, include_archived=False):
            assert attachment_id == 50
            assert session is fake_session
            return attachment_factory()

        monkeypatch.setattr(
            attachments_router, "get_attachment_by_id", fake_get_attachment_by_id
        )

        result = attachments_router.get_attachment_by_id_route(50, fake_session)

        assert result == attachments_router.AttachmentWithContextOut.model_validate(
            attachment_factory()
        )

    def test_returns_404_when_attachment_is_not_found(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_attachment_by_id(attachment_id, session, include_archived=False):
            return None

        monkeypatch.setattr(
            attachments_router, "get_attachment_by_id", fake_get_attachment_by_id
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.get_attachment_by_id_route(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Attachment 999 not found."

    def test_registers_attachment_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/attachments/{attachment_id}"
        )

        assert route.response_model is attachments_router.AttachmentWithContextOut


class TestPostNewAttachmentRoute:
    def test_client_returns_attachment_json_when_created(
        self, main_module, client, mock_db, monkeypatch, attachment_create_factory
    ):
        new_attachment = attachments_router.AttachmentOut.model_validate(
            {
                **attachment_create_factory(),
                "id": 50,
                "uploaded_at": datetime(2026, 4, 3, 9, 30),
                "inspection_date": date(2026, 4, 1),
                "regulation_id": 5,
                "regulation_title": "USDA Organic",
            }
        )

        def fake_post_new_attachment(attachment, session):
            assert attachment.file_type == "pdf"
            assert attachment.file_name == "evidence"
            assert attachment.certification_id == 100
            assert session is mock_db
            return new_attachment

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        response = client.post("/attachments", json=attachment_create_factory())

        assert response.status_code == 201
        assert response.json() == {
            "file_type": "pdf",
            "file_name": "evidence",
            "certification_id": 100,
            "description": "Inspection evidence",
            "finding_ids": [],
            "id": 50,
            "uploaded_at": "2026-04-03T09:30:00",
            "inspection_date": "2026-04-01",
            "regulation_id": 5,
            "regulation_title": "USDA Organic",
            "archived_at": None,
            "archive_reason": None,
        }

    def test_client_returns_404_when_certification_is_not_found(
        self, main_module, client, mock_db, monkeypatch, attachment_create_factory
    ):
        def fake_post_new_attachment(attachment, session):
            assert attachment.certification_id == 100
            assert session is mock_db
            raise attachments_router.AttachmentCertificationNotFoundError(
                "Certification 100 does not exist."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        response = client.post("/attachments", json=attachment_create_factory())

        assert response.status_code == 404
        assert response.json() == {"detail": "Certification 100 does not exist."}

    def test_client_returns_422_when_finding_belongs_to_another_certification(
        self, main_module, client, mock_db, monkeypatch, attachment_create_factory
    ):
        def fake_post_new_attachment(attachment, session):
            assert attachment.finding_ids == [7]
            assert session is mock_db
            raise attachments_router.AttachmentFindingCertificationMismatchError(
                "Finding 7 does not belong to certification 100."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        response = client.post(
            "/attachments", json=attachment_create_factory(finding_ids=[7])
        )

        assert response.status_code == 422
        assert response.json() == {
            "detail": "Finding 7 does not belong to certification 100."
        }

    def test_client_returns_409_when_attachment_conflicts(
        self, main_module, client, mock_db, monkeypatch, attachment_create_factory
    ):
        def fake_post_new_attachment(attachment, session):
            assert session is mock_db
            raise attachments_router.AttachmentConflictError(
                "Attachment could not be created."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        response = client.post("/attachments", json=attachment_create_factory())

        assert response.status_code == 409
        assert response.json() == {"detail": "Attachment could not be created."}

    def test_client_returns_422_when_attachment_is_invalid(self, client):
        response = client.post("/attachments", json={"file_type": "pdf"})

        assert response.status_code == 422

    def test_returns_404_when_certification_is_not_found(
        self, main_module, monkeypatch, attachment_create_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory()
        )

        def fake_post_new_attachment(attachment_info, session):
            raise attachments_router.AttachmentCertificationNotFoundError(
                "Certification 100 does not exist."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(attachment, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Certification 100 does not exist."

    def test_returns_404_when_finding_is_not_found(
        self, main_module, monkeypatch, attachment_create_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory(finding_ids=[7])
        )

        def fake_post_new_attachment(attachment_info, session):
            raise attachments_router.AttachmentFindingNotFoundError(
                "Finding 7 does not exist."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(attachment, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Finding 7 does not exist."

    def test_returns_422_when_finding_belongs_to_another_certification(
        self, main_module, monkeypatch, attachment_create_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory(finding_ids=[7])
        )

        def fake_post_new_attachment(attachment_info, session):
            raise attachments_router.AttachmentFindingCertificationMismatchError(
                "Finding 7 does not belong to certification 100."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(attachment, object())

        assert exc_info.value.status_code == 422
        assert (
            exc_info.value.detail == "Finding 7 does not belong to certification 100."
        )

    def test_returns_409_when_attachment_conflicts(
        self, main_module, monkeypatch, attachment_create_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory()
        )

        def fake_post_new_attachment(attachment_info, session):
            raise attachments_router.AttachmentConflictError(
                "Attachment could not be created."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(attachment, object())

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Attachment could not be created."
