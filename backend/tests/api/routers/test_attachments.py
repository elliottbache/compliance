from datetime import UTC, date, datetime

import pytest
from compliance.api.routers import attachments as attachments_router
from fastapi import HTTPException


def attachment_out_factory(**overrides):
    """Build an attachment list response payload for route tests."""
    data = {
        "file_name": "evidence",
        "file_path": "dummy/evidence.pdf",
        "certification_id": 100,
        "description": "Inspection evidence",
        "finding_ids": [1],
        "id": 50,
        "uploaded_at": datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
        "archived_at": None,
        "archive_reason": None,
        "inspection_date": date(2026, 4, 1),
        "regulation_id": 5,
        "regulation_title": "USDA Organic",
    }
    data.update(overrides)
    return attachments_router.AttachmentOut.model_validate(data)


class TestGetAttachmentsRoute:
    def test_route_returns_attachments_json(self, client, mock_db, monkeypatch):
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
                "file_name": "evidence",
                "file_path": "dummy/evidence.pdf",
                "certification_id": 100,
                "description": "Inspection evidence",
                "finding_ids": [1],
                "id": 50,
                "uploaded_at": "2026-04-03T09:30:00Z",
                "inspection_date": "2026-04-01",
                "regulation_id": 5,
                "regulation_title": "USDA Organic",
                "archived_at": None,
                "archive_reason": None,
            }
        ]

    def test_route_passes_query_filters_to_service(self, client, mock_db, monkeypatch):
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

    def test_route_excludes_archived_attachments_by_default(
        self, client, mock_db, monkeypatch
    ):
        archived_attachment_id = 51

        def fake_get_attachments(
            session,
            site_id,
            certification_id,
            rule_id,
            finding_id,
            include_archived=False,
        ):
            assert session is mock_db
            assert include_archived is False
            return [attachment_out_factory()]

        monkeypatch.setattr(
            attachments_router,
            "get_attachments",
            fake_get_attachments,
        )

        response = client.get("/attachments")

        assert response.status_code == 200
        returned_ids = {attachment["id"] for attachment in response.json()}
        assert 50 in returned_ids
        assert archived_attachment_id not in returned_ids

    def test_route_include_archived_returns_archived_attachment(
        self, client, mock_db, monkeypatch
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)
        archived_attachment_id = 51

        def fake_get_attachments(
            session,
            site_id,
            certification_id,
            rule_id,
            finding_id,
            include_archived=False,
        ):
            assert session is mock_db
            assert include_archived is True
            return [
                attachment_out_factory(),
                attachment_out_factory(
                    id=archived_attachment_id,
                    archived_at=archived_at,
                    archive_reason="obsolete",
                ),
            ]

        monkeypatch.setattr(
            attachments_router,
            "get_attachments",
            fake_get_attachments,
        )

        response = client.get("/attachments?include_archived=true")

        assert response.status_code == 200
        returned_ids = {attachment["id"] for attachment in response.json()}
        assert archived_attachment_id in returned_ids

    def test_route_returns_422_when_filter_type_is_invalid(self, client):
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
    def test_route_returns_attachment_without_findings(
        self, main_module, client, mock_db, monkeypatch, attachment_factory
    ):
        def fake_get_attachment_by_id(session, attachment_id, include_archived=False):
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
            "file_name": "evidence",
            "file_path": "dummy/evidence.pdf",
            "description": "Inspection evidence",
            "uploaded_at": "2026-04-03T09:30:00Z",
            "archived_at": None,
            "archive_reason": None,
            "certification_id": 100,
            "inspection_date": "2026-04-01",
            "regulation_id": 5,
            "regulation_title": "USDA Organic",
            "finding_links": [],
        }

    def test_route_returns_attachment_with_two_findings(
        self, main_module, client, mock_db, monkeypatch, attachment_factory
    ):
        def fake_get_attachment_by_id(session, attachment_id, include_archived=False):
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

    def test_route_returns_404_when_attachment_is_not_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_attachment_by_id(session, attachment_id, include_archived=False):
            assert attachment_id == 999
            assert session is mock_db
            return None

        monkeypatch.setattr(
            attachments_router, "get_attachment_by_id", fake_get_attachment_by_id
        )

        response = client.get("/attachments/999")

        assert response.status_code == 404
        assert response.json() == {"detail": "Attachment 999 not found."}

    def test_route_returns_422_when_attachment_id_is_not_an_int(self, client):
        response = client.get("/attachments/not-an-int")

        assert response.status_code == 422

    def test_returns_attachment_when_found(
        self, main_module, monkeypatch, attachment_factory
    ) -> None:
        fake_session = object()

        def fake_get_attachment_by_id(session, attachment_id, include_archived=False):
            assert attachment_id == 50
            assert session is fake_session
            return attachment_factory()

        monkeypatch.setattr(
            attachments_router, "get_attachment_by_id", fake_get_attachment_by_id
        )

        result = attachments_router.get_attachment_by_id_route(fake_session, 50)

        assert result == attachments_router.AttachmentWithContextOut.model_validate(
            attachment_factory()
        )

    def test_returns_404_when_attachment_is_not_found(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_attachment_by_id(session, attachment_id, include_archived=False):
            return None

        monkeypatch.setattr(
            attachments_router, "get_attachment_by_id", fake_get_attachment_by_id
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.get_attachment_by_id_route(object(), 999)

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
    def test_route_returns_attachment_json_when_created(
        self, client, mock_db, monkeypatch, attachment_create_factory
    ):
        new_attachment = attachments_router.AttachmentOut.model_validate(
            {
                **attachment_create_factory(),
                "id": 50,
                "file_path": "dummy/evidence.pdf",
                "uploaded_at": datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
                "inspection_date": date(2026, 4, 1),
                "regulation_id": 5,
                "regulation_title": "USDA Organic",
            }
        )

        def fake_post_new_attachment(session, attachment):
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
            "file_name": "evidence",
            "file_path": "dummy/evidence.pdf",
            "certification_id": 100,
            "description": "Inspection evidence",
            "finding_ids": [],
            "id": 50,
            "uploaded_at": "2026-04-03T09:30:00Z",
            "inspection_date": "2026-04-01",
            "regulation_id": 5,
            "regulation_title": "USDA Organic",
            "archived_at": None,
            "archive_reason": None,
        }

    def test_route_returns_404_when_certification_is_not_found(
        self, main_module, client, mock_db, monkeypatch, attachment_create_factory
    ):
        def fake_post_new_attachment(session, attachment):
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

    def test_route_returns_422_when_finding_belongs_to_another_certification(
        self, main_module, client, mock_db, monkeypatch, attachment_create_factory
    ):
        def fake_post_new_attachment(session, attachment):
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

    def test_route_returns_409_when_attachment_conflicts(
        self, main_module, client, mock_db, monkeypatch, attachment_create_factory
    ):
        def fake_post_new_attachment(session, attachment):
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

    def test_route_returns_422_when_attachment_is_invalid(self, client):
        response = client.post("/attachments", json={"file_name": "test.pdf"})

        assert response.status_code == 422

    def test_returns_404_when_certification_is_not_found(
        self, main_module, monkeypatch, attachment_create_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory()
        )

        def fake_post_new_attachment(session, attachment_info):
            raise attachments_router.AttachmentCertificationNotFoundError(
                "Certification 100 does not exist."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(object(), attachment)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Certification 100 does not exist."

    def test_returns_404_when_finding_is_not_found(
        self, main_module, monkeypatch, attachment_create_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory(finding_ids=[7])
        )

        def fake_post_new_attachment(session, attachment_info):
            raise attachments_router.AttachmentFindingNotFoundError(
                "Finding 7 does not exist."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(object(), attachment)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Finding 7 does not exist."

    def test_returns_422_when_finding_belongs_to_another_certification(
        self, main_module, monkeypatch, attachment_create_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory(finding_ids=[7])
        )

        def fake_post_new_attachment(session, attachment_info):
            raise attachments_router.AttachmentFindingCertificationMismatchError(
                "Finding 7 does not belong to certification 100."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(object(), attachment)

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

        def fake_post_new_attachment(session, attachment_info):
            raise attachments_router.AttachmentConflictError(
                "Attachment could not be created."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(object(), attachment)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Attachment could not be created."


class TestPostAttachmentUploadRoute:
    # route calls service
    # maps attachment errors to 404/422/409
    # validates missing file
    pass


class TestPostAttachmentArchivedByIdRoute:
    # TestClient
    def test_route_archives_active_attachment(
        self, client, mock_db, monkeypatch, attachment_factory
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)

        def fake_post_attachment_archived_by_id(
            session, attachment_id, *, archive_request
        ):
            assert session is mock_db
            assert attachment_id == 50
            assert archive_request.archive_reason == "duplicate"
            return attachment_factory(
                archived_at=archived_at, archive_reason="duplicate"
            )

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_archived_by_id",
            fake_post_attachment_archived_by_id,
        )

        response = client.post(
            "/attachments/50/archive", json={"archive_reason": "duplicate"}
        )

        assert response.status_code == 200
        assert response.json()["archived_at"] is not None
        assert response.json()["archive_reason"] == "duplicate"

    def test_route_archive_already_archived_attachment_returns_200(
        self, client, mock_db, monkeypatch, attachment_factory
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)

        def fake_post_attachment_archived_by_id(
            session, attachment_id, *, archive_request
        ):
            assert session is mock_db
            assert attachment_id == 50
            return attachment_factory(
                archived_at=archived_at, archive_reason="old reason"
            )

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_archived_by_id",
            fake_post_attachment_archived_by_id,
        )

        response = client.post(
            "/attachments/50/archive", json={"archive_reason": "old reason"}
        )

        assert response.status_code == 200
        assert response.json()["archived_at"] is not None

    def test_route_returns_404_when_attachment_does_not_exist(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_attachment_archived_by_id(
            session, attachment_id, *, archive_request
        ):
            assert session is mock_db
            assert attachment_id == 50
            return None

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_archived_by_id",
            fake_post_attachment_archived_by_id,
        )

        response = client.post("/attachments/50/archive")

        assert response.status_code == 404
        assert response.json() == {"detail": "Attachment does not exist: 50."}

    def test_route_returns_422_when_attachment_id_is_invalid(self, client):
        response = client.post("/attachments/not-an-id/archive")

        assert response.status_code == 422

    def test_defaults_missing_archive_request(self, monkeypatch) -> None:
        fake_session = object()
        expected = attachments_router.AttachmentWithContextOut(
            id=50,
            file_name="evidence",
            file_path="dummy/evidence.pdf",
            description="Inspection evidence",
            uploaded_at=datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
            archived_at=None,
            archive_reason=None,
            certification_id=100,
            inspection_date=date(2026, 4, 1),
            regulation_id=5,
            regulation_title="USDA Organic",
            finding_links=[],
        )

        def fake_post_attachment_archived_by_id(
            session, attachment_id, *, archive_request
        ):
            assert session is fake_session
            assert attachment_id == 50
            assert archive_request == attachments_router.ArchiveRequest()
            return expected

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_archived_by_id",
            fake_post_attachment_archived_by_id,
        )

        result = attachments_router.post_attachment_archived_by_id_route(
            fake_session, 50
        )

        assert result == expected

    def test_returns_404_when_attachment_does_not_exist(self, monkeypatch) -> None:
        def fake_post_attachment_archived_by_id(
            session, attachment_id, *, archive_request
        ):
            return None

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_archived_by_id",
            fake_post_attachment_archived_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_attachment_archived_by_id_route(object(), 50)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Attachment does not exist: 50."


class TestPostAttachmentRestoredByIdRoute:
    # TestClient
    def test_route_restores_archived_attachment(
        self, client, mock_db, monkeypatch, attachment_factory
    ):
        def fake_post_attachment_restored_by_id(session, attachment_id):
            assert session is mock_db
            assert attachment_id == 50
            return attachment_factory(archived_at=None, archive_reason=None)

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_restored_by_id",
            fake_post_attachment_restored_by_id,
        )

        response = client.post("/attachments/50/restore")

        assert response.status_code == 200
        response_json = response.json()
        assert response_json["archived_at"] is None
        assert response_json["archive_reason"] is None

    def test_route_restore_active_attachment_returns_200(
        self, client, mock_db, monkeypatch, attachment_factory
    ):
        def fake_post_attachment_restored_by_id(session, attachment_id):
            assert session is mock_db
            assert attachment_id == 50
            return attachment_factory(archived_at=None, archive_reason=None)

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_restored_by_id",
            fake_post_attachment_restored_by_id,
        )

        response = client.post("/attachments/50/restore")

        assert response.status_code == 200
        assert response.json()["archived_at"] is None

    def test_route_returns_404_when_attachment_does_not_exist(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_attachment_restored_by_id(session, attachment_id):
            assert session is mock_db
            assert attachment_id == 50
            return None

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_restored_by_id",
            fake_post_attachment_restored_by_id,
        )

        response = client.post("/attachments/50/restore")

        assert response.status_code == 404
        assert response.json() == {"detail": "Attachment does not exist: 50."}

    def test_route_returns_422_when_attachment_id_is_invalid(self, client):
        response = client.post("/attachments/not-an-id/restore")

        assert response.status_code == 422

    def test_returns_restored_attachment(self, monkeypatch) -> None:
        fake_session = object()
        expected = attachments_router.AttachmentWithContextOut(
            id=50,
            file_name="evidence",
            file_path="dummy/evidence.pdf",
            description="Inspection evidence",
            uploaded_at=datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
            archived_at=None,
            archive_reason=None,
            certification_id=100,
            inspection_date=date(2026, 4, 1),
            regulation_id=5,
            regulation_title="USDA Organic",
            finding_links=[],
        )

        def fake_post_attachment_restored_by_id(session, attachment_id):
            assert session is fake_session
            assert attachment_id == 50
            return expected

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_restored_by_id",
            fake_post_attachment_restored_by_id,
        )

        result = attachments_router.post_attachment_restored_by_id_route(
            fake_session, 50
        )

        assert result == expected

    def test_returns_404_when_attachment_does_not_exist(self, monkeypatch) -> None:
        def fake_post_attachment_restored_by_id(session, attachment_id):
            return None

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_restored_by_id",
            fake_post_attachment_restored_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_attachment_restored_by_id_route(object(), 50)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Attachment does not exist: 50."
