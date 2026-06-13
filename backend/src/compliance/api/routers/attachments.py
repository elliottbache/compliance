from typing import Annotated

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    ArchiveRequest,
    AttachmentCreate,
    AttachmentOut,
    AttachmentWithContextOut,
)
from compliance.auth.authorization import require_role
from compliance.db.models import Role
from compliance.services.attachments import (
    AttachmentCertificationNotFoundError,
    AttachmentConflictError,
    AttachmentFileError,
    AttachmentFindingCertificationMismatchError,
    AttachmentFindingNotFoundError,
    AttachmentNotFoundError,
    AttachmentPermissionError,
    AttachmentRuleNotFoundError,
    AttachmentSiteNotFoundError,
    get_attachment_download,
    get_attachments,
    post_attachment_archived_by_id,
    post_attachment_restored_by_id,
    post_attachment_upload,
    post_new_attachment,
)
from compliance.services.schemas import UserOut
from fastapi import APIRouter, Depends, Form, HTTPException, Path, Query, UploadFile
from fastapi.responses import FileResponse

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.get("")
def get_attachments_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.VIEWER))],
    site_id: Annotated[int | None, Query(gt=0)] = None,
    certification_id: Annotated[int | None, Query(gt=0)] = None,
    rule_id: Annotated[int | None, Query(gt=0)] = None,
    finding_id: Annotated[int | None, Query(gt=0)] = None,
    include_archived: Annotated[bool, Query()] = False,
) -> list[AttachmentOut]:
    """Return attachments with optional filters.

    Args:
        session: Database session provided by FastAPI dependency injection.
        site_id: Optional site identifier used to limit attachments to one site.
        certification_id: Optional certification identifier used to limit attachments
            to one certification.
        rule_id: Optional rule identifier used to limit attachments to one rule.
        finding_id: Optional finding identifier used to limit attachments to one
            finding.
        include_archived: When true, include archived attachments and related
            certification, site, regulation, finding, and rule context. By
            default, archived optional finding and rule links are omitted
            without hiding otherwise visible attachments.

    Returns:
        Attachment records serialized with certification, regulation, and linked
        finding ID context.

    Raises:
        HTTPException: If a requested site, certification, rule, or finding
            filter references a missing visible record.
    """
    try:
        attachments = get_attachments(
            session,
            site_id=site_id,
            certification_id=certification_id,
            rule_id=rule_id,
            finding_id=finding_id,
            include_archived=include_archived,
        )
    except AttachmentSiteNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Missing site {site_id}.") from err
    except AttachmentCertificationNotFoundError as err:
        raise HTTPException(
            status_code=404, detail=f"Missing certification {certification_id}."
        ) from err
    except AttachmentRuleNotFoundError as err:
        raise HTTPException(status_code=404, detail=f"Missing rule {rule_id}.") from err
    except AttachmentFindingNotFoundError as err:
        raise HTTPException(
            status_code=404, detail=f"Missing finding {finding_id}."
        ) from err

    return attachments


@router.get("/{attachment_id}/download")
def get_attachment_download_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.VIEWER))],
    attachment_id: Annotated[int, Path(ge=1)],
) -> FileResponse:
    """Download the stored file for one attachment.

    Args:
        session: Database session provided by FastAPI dependency injection.
        attachment_id: Primary key of the attachment whose file should be
            downloaded.

    Returns:
        A file response with a browser-facing filename.

    Raises:
        HTTPException: If the attachment metadata or stored file cannot be found.
    """

    try:
        file_name, file_path = get_attachment_download(session, attachment_id)

    except AttachmentNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Attachment with ID {attachment_id} not found."
        ) from exc

    except AttachmentFileError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Attachment file does not exist or not found: {exc}.",
        ) from exc

    return FileResponse(
        path=file_path, filename=file_name, media_type="application/octet-stream"
    )


@router.post("", status_code=201)
def post_new_attachment_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.INSPECTOR))],
    attachment: AttachmentCreate,
) -> AttachmentOut:
    """Create a new attachment metadata record.

    Args:
        session: Database session provided by FastAPI dependency injection.
        attachment: Attachment metadata supplied in the request body.

    Returns:
        Created attachment metadata with generated storage and certification
        context fields.

    Raises:
        HTTPException: If the parent certification or linked findings are
            missing, if a finding belongs to another certification, or if the
            attachment conflicts with existing stored data.
    """
    try:
        new_attachment = post_new_attachment(session, attachment, _authorized_user.id)
    except AttachmentCertificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AttachmentFindingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AttachmentPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AttachmentFindingCertificationMismatchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AttachmentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return AttachmentOut.model_validate(new_attachment)


@router.post("/upload", status_code=201)
def post_attachment_upload_route(
    session: SessionDep,
    file: UploadFile,
    id: Annotated[int, Form()],
) -> None:
    """Upload a file for an existing attachment metadata record.

    Args:
        session: Database session provided by FastAPI dependency injection.
        file: Uploaded file supplied as multipart form data.
        id: Attachment metadata ID supplied as multipart form data.

    Raises:
        HTTPException: If the upload is invalid, the attachment metadata is
        missing, or the file cannot be persisted.
    """
    # call attachment upload service
    try:
        post_attachment_upload(
            session,
            attachment_id=id,
            file_size=file.size,
            file_type=file.content_type,
            file_name=file.filename,
            file_stream=file.file,
        )
    except AttachmentFileError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Attachment could not be uploaded: {file.filename} with type {file.content_type} and size {file.size}.",
        ) from exc
    except AttachmentConflictError as exc:
        raise HTTPException(
            status_code=500, detail=f"File persistence error for file: {file.filename}."
        ) from exc
    except AttachmentNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Attachment with ID {id} not found."
        ) from exc
    finally:
        file.file.close()


@router.post("/{attachment_id}/archive", status_code=200)
def post_attachment_archived_by_id_route(
    session: SessionDep,
    attachment_id: Annotated[int, Path(ge=1)],
    archive_request: ArchiveRequest | None = None,
) -> AttachmentWithContextOut:
    """Archive one attachment by ID."""
    archive_request = archive_request or ArchiveRequest()

    attachment = post_attachment_archived_by_id(
        session, attachment_id, archive_request=archive_request
    )
    if attachment is None:
        raise HTTPException(
            status_code=404, detail=f"Attachment does not exist: {attachment_id}."
        )

    return AttachmentWithContextOut.model_validate(attachment)


@router.post("/{attachment_id}/restore", status_code=200)
def post_attachment_restored_by_id_route(
    session: SessionDep, attachment_id: Annotated[int, Path(ge=1)]
) -> AttachmentWithContextOut:
    """Restore one archived attachment by ID."""
    attachment = post_attachment_restored_by_id(session, attachment_id)
    if attachment is None:
        raise HTTPException(
            status_code=404, detail=f"Attachment does not exist: {attachment_id}."
        )

    return AttachmentWithContextOut.model_validate(attachment)
