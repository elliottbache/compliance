from datetime import date

import pytest
from fastapi import HTTPException

from compliance.api.routers import attachments as attachments_router


class TestGetAttachmentByIdRoute:
    def test_client_returns_attachment_without_findings(
        self, main_module, client, mock_db, monkeypatch, attachment_factory
    ):
        def fake_get_attachment_by_id(attachment_id, session):
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
            "uploaded_at": "2026-04-03",
            "certification_id": 100,
            "inspection_date": "2026-04-01",
            "regulation_id": 5,
            "regulation_title": "USDA Organic",
            "finding_links": [],
        }

    def test_client_returns_attachment_with_two_findings(
        self, main_module, client, mock_db, monkeypatch, attachment_factory
    ):
        def fake_get_attachment_by_id(attachment_id, session):
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
        def fake_get_attachment_by_id(attachment_id, session):
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

        def fake_get_attachment_by_id(attachment_id, session):
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
        def fake_get_attachment_by_id(attachment_id, session):
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
                "uploaded_at": date(2026, 4, 3),
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
            "uploaded_at": "2026-04-03",
            "inspection_date": "2026-04-01",
            "regulation_id": 5,
            "regulation_title": "USDA Organic",
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
