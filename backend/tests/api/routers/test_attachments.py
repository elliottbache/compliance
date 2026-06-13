from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

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


@pytest.mark.usefixtures("viewer_user_override")
class TestGetAttachmentsRouteClient:
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


class TestGetAttachmentsRouteUnit:

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
            _authorized_user=object(),
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
            attachments_router.get_attachments_route(
                object(), _authorized_user=object(), site_id=999
            )

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
            attachments_router.get_attachments_route(
                object(), _authorized_user=object(), certification_id=999
            )

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
            attachments_router.get_attachments_route(
                object(), _authorized_user=object(), rule_id=999
            )

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
            attachments_router.get_attachments_route(
                object(), _authorized_user=object(), finding_id=999
            )

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


class TestGetAttachmentDownloadRoute:
    def test_returns_file_response_when_attachment_file_exists(
        self, monkeypatch, tmp_path
    ) -> None:
        fake_session = object()
        stored_file = tmp_path / "stored-file.pdf"
        stored_file.write_bytes(b"evidence")

        def fake_get_attachment_download(session, attachment_id):
            assert session is fake_session
            assert attachment_id == 50
            return "inspection_report.pdf", stored_file

        monkeypatch.setattr(
            attachments_router,
            "get_attachment_download",
            fake_get_attachment_download,
        )

        response = attachments_router.get_attachment_download_route(
            fake_session,
            _authorized_user=object(),
            attachment_id=50,
        )

        assert response.path == stored_file
        assert response.media_type == "application/octet-stream"
        assert (
            response.headers["content-disposition"]
            == 'attachment; filename="inspection_report.pdf"'
        )

    def test_returns_404_when_attachment_id_does_not_exist(self, monkeypatch) -> None:
        def fake_get_attachment_download(session, attachment_id):
            assert attachment_id == 999
            raise attachments_router.AttachmentNotFoundError(attachment_id)

        monkeypatch.setattr(
            attachments_router,
            "get_attachment_download",
            fake_get_attachment_download,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.get_attachment_download_route(
                object(),
                _authorized_user=object(),
                attachment_id=999,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Attachment with ID 999 not found."

    def test_returns_404_when_attachment_file_does_not_exist(self, monkeypatch) -> None:
        def fake_get_attachment_download(session, attachment_id):
            raise attachments_router.AttachmentFileError(
                attachment_id, Path("missing.pdf")
            )

        monkeypatch.setattr(
            attachments_router,
            "get_attachment_download",
            fake_get_attachment_download,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.get_attachment_download_route(
                object(),
                _authorized_user=object(),
                attachment_id=50,
            )

        assert exc_info.value.status_code == 404
        assert "Attachment file does not exist or not found:" in exc_info.value.detail


@pytest.mark.usefixtures("inspector_user_override")
class TestPostNewAttachmentRouteClient:
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

        def fake_post_new_attachment(session, attachment, user_id):
            assert attachment.file_name == "evidence"
            assert attachment.certification_id == 100
            assert session is mock_db
            assert user_id == 10
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
        def fake_post_new_attachment(session, attachment, user_id):
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

    def test_route_returns_403_when_certification_belongs_to_another_inspector(
        self, main_module, client, mock_db, monkeypatch, attachment_create_factory
    ):
        def fake_post_new_attachment(session, attachment, user_id):
            assert session is mock_db
            assert user_id == 10
            raise attachments_router.AttachmentPermissionError(
                "Certification 100 is assigned to inspector 11.  "
                "You are logged in as inspector 10."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        response = client.post("/attachments", json=attachment_create_factory())

        assert response.status_code == 403
        assert response.json() == {
            "detail": (
                "Certification 100 is assigned to inspector 11.  "
                "You are logged in as inspector 10."
            )
        }

    def test_route_returns_422_when_finding_belongs_to_another_certification(
        self, main_module, client, mock_db, monkeypatch, attachment_create_factory
    ):
        def fake_post_new_attachment(session, attachment, user_id):
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
        def fake_post_new_attachment(session, attachment, user_id):
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


class TestPostNewAttachmentRouteUnit:

    def test_returns_404_when_certification_is_not_found(
        self, main_module, monkeypatch, attachment_create_factory, user_record_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory()
        )

        def fake_post_new_attachment(session, attachment_info, user_id):
            raise attachments_router.AttachmentCertificationNotFoundError(
                "Certification 100 does not exist."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(
                object(),
                _authorized_user=user_record_factory(),
                attachment=attachment,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Certification 100 does not exist."

    def test_returns_403_when_certification_belongs_to_another_inspector(
        self, main_module, monkeypatch, attachment_create_factory, user_record_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory()
        )
        authorized_user = user_record_factory(id=10)

        def fake_post_new_attachment(session, attachment_info, user_id):
            assert user_id == authorized_user.id
            raise attachments_router.AttachmentPermissionError(
                "Certification 100 is assigned to inspector 11.  "
                "You are logged in as inspector 10."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(
                object(),
                _authorized_user=authorized_user,
                attachment=attachment,
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == (
            "Certification 100 is assigned to inspector 11.  "
            "You are logged in as inspector 10."
        )

    def test_returns_404_when_finding_is_not_found(
        self, main_module, monkeypatch, attachment_create_factory, user_record_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory(finding_ids=[7])
        )

        def fake_post_new_attachment(session, attachment_info, user_id):
            raise attachments_router.AttachmentFindingNotFoundError(
                "Finding 7 does not exist."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(
                object(),
                _authorized_user=user_record_factory(),
                attachment=attachment,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Finding 7 does not exist."

    def test_returns_422_when_finding_belongs_to_another_certification(
        self, main_module, monkeypatch, attachment_create_factory, user_record_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory(finding_ids=[7])
        )

        def fake_post_new_attachment(session, attachment_info, user_id):
            raise attachments_router.AttachmentFindingCertificationMismatchError(
                "Finding 7 does not belong to certification 100."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(
                object(),
                _authorized_user=user_record_factory(),
                attachment=attachment,
            )

        assert exc_info.value.status_code == 422
        assert (
            exc_info.value.detail == "Finding 7 does not belong to certification 100."
        )

    def test_returns_409_when_attachment_conflicts(
        self, main_module, monkeypatch, attachment_create_factory, user_record_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory()
        )

        def fake_post_new_attachment(session, attachment_info, user_id):
            raise attachments_router.AttachmentConflictError(
                "Attachment could not be created."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(
                object(),
                _authorized_user=user_record_factory(),
                attachment=attachment,
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Attachment could not be created."


class TestPostAttachmentUploadRouteClient:
    def test_route_uploads_attachment_file(self, client, mock_db, monkeypatch):
        def fake_post_attachment_upload(
            session,
            *,
            attachment_id,
            file_size,
            file_type,
            file_name,
            file_stream,
        ):
            assert session is mock_db
            assert attachment_id == 50
            assert file_size == 11
            assert file_type == "application/pdf"
            assert file_name == "evidence.pdf"
            assert file_stream.read() == b"hello world"

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_upload",
            fake_post_attachment_upload,
        )

        response = client.post(
            "/attachments/upload",
            data={"id": "50"},
            files={"file": ("evidence.pdf", b"hello world", "application/pdf")},
        )

        assert response.status_code == 201

    def test_route_returns_422_when_file_is_missing(self, client):
        response = client.post("/attachments/upload", data={"id": "50"})

        assert response.status_code == 422

    def test_route_returns_400_when_upload_file_is_invalid(self, client, monkeypatch):
        def fake_post_attachment_upload(session, **kwargs):
            raise attachments_router.AttachmentFileError()

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_upload",
            fake_post_attachment_upload,
        )

        response = client.post(
            "/attachments/upload",
            data={"id": "50"},
            files={"file": ("evidence.exe", b"data", "application/x-msdownload")},
        )

        assert response.status_code == 400
        assert response.json() == {
            "detail": (
                "Attachment could not be uploaded: evidence.exe with type "
                "application/x-msdownload and size 4."
            )
        }

    def test_route_returns_404_when_upload_attachment_id_does_not_exist(
        self, client, monkeypatch
    ):
        def fake_post_attachment_upload(session, **kwargs):
            raise attachments_router.AttachmentNotFoundError()

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_upload",
            fake_post_attachment_upload,
        )

        response = client.post(
            "/attachments/upload",
            data={"id": "999"},
            files={"file": ("evidence.pdf", b"data", "application/pdf")},
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "Attachment with ID 999 not found."}


class TestPostAttachmentUploadRouteUnit:

    def test_returns_none_when_upload_succeeds(self, monkeypatch) -> None:
        fake_file = SimpleNamespace(
            filename="evidence.pdf",
            content_type="application/pdf",
            size=4,
            file=BytesIO(b"data"),
        )

        def fake_post_attachment_upload(
            session,
            *,
            attachment_id,
            file_size,
            file_type,
            file_name,
            file_stream,
        ):
            assert attachment_id == 50
            assert file_size == 4
            assert file_type == "application/pdf"
            assert file_name == "evidence.pdf"
            assert file_stream.read() == b"data"

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_upload",
            fake_post_attachment_upload,
        )

        result = attachments_router.post_attachment_upload_route(
            object(), fake_file, 50
        )

        assert result is None
        assert fake_file.file.closed

    def test_returns_400_when_file_is_invalid(self, monkeypatch) -> None:
        fake_file = SimpleNamespace(
            filename="evidence.exe",
            content_type="application/x-msdownload",
            size=4,
            file=BytesIO(b"data"),
        )

        def fake_post_attachment_upload(session, **kwargs):
            raise attachments_router.AttachmentFileError()

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_upload",
            fake_post_attachment_upload,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_attachment_upload_route(object(), fake_file, 50)

        assert exc_info.value.status_code == 400
        assert (
            exc_info.value.detail
            == "Attachment could not be uploaded: evidence.exe with type "
            "application/x-msdownload and size 4."
        )
        assert fake_file.file.closed

    def test_returns_404_when_attachment_is_not_found(self, monkeypatch) -> None:
        fake_file = SimpleNamespace(
            filename="evidence.pdf",
            content_type="application/pdf",
            size=4,
            file=BytesIO(b"data"),
        )

        def fake_post_attachment_upload(session, **kwargs):
            raise attachments_router.AttachmentNotFoundError()

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_upload",
            fake_post_attachment_upload,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_attachment_upload_route(object(), fake_file, 50)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Attachment with ID 50 not found."
        assert fake_file.file.closed

    def test_returns_500_when_file_persistence_fails(self, monkeypatch) -> None:
        fake_file = SimpleNamespace(
            filename="evidence.pdf",
            content_type="application/pdf",
            size=4,
            file=BytesIO(b"data"),
        )

        def fake_post_attachment_upload(session, **kwargs):
            raise attachments_router.AttachmentConflictError()

        monkeypatch.setattr(
            attachments_router,
            "post_attachment_upload",
            fake_post_attachment_upload,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_attachment_upload_route(object(), fake_file, 50)

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "File persistence error for file: evidence.pdf."
        assert fake_file.file.closed


class TestPostAttachmentArchivedByIdRouteClient:
    # TestClient
    def test_route_archives_active_attachment(
        self,
        client,
        mock_db,
        monkeypatch,
        attachment_factory,
        assert_archived_response,
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
        assert_archived_response(response.json(), "duplicate")

    def test_route_archive_already_archived_attachment_returns_200(
        self,
        client,
        mock_db,
        monkeypatch,
        attachment_factory,
        assert_archived_response,
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
        assert_archived_response(response.json())

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


class TestPostAttachmentArchivedByIdRouteUnit:

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


class TestPostAttachmentRestoredByIdRouteClient:
    # TestClient
    def test_route_restores_archived_attachment(
        self,
        client,
        mock_db,
        monkeypatch,
        attachment_factory,
        assert_restored_response,
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
        assert_restored_response(response_json)

    def test_route_restore_active_attachment_returns_200(
        self,
        client,
        mock_db,
        monkeypatch,
        attachment_factory,
        assert_restored_response,
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
        assert_restored_response(response.json())

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


class TestPostAttachmentRestoredByIdRouteUnit:

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
