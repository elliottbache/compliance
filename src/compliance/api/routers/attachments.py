from fastapi import APIRouter, HTTPException

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    AttachmentCreate,
    AttachmentOut,
    AttachmentWithContextOut,
)
from compliance.services.query_db import (
    AttachmentCertificationNotFoundError,
    AttachmentConflictError,
    AttachmentFindingCertificationMismatchError,
    AttachmentFindingNotFoundError,
    get_attachment_by_id,
    post_new_attachment,
)

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.get("/{attachment_id}")
def get_attachment_by_id_route(
    attachment_id: int, session: SessionDep
) -> AttachmentWithContextOut:
    """Return one attachment with certification, regulation, and finding context.

    Args:
        attachment_id: Unique identifier for the attachment to retrieve.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Attachment details serialized with certification, regulation, and
        linked finding context.

    Raises:
        HTTPException: If no attachment exists for the requested ID.
    """
    result = get_attachment_by_id(attachment_id, session)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Attachment {attachment_id} not found."
        )

    return AttachmentWithContextOut.model_validate(result)


@router.post("", status_code=201)
def post_new_attachment_route(
    attachment: AttachmentCreate, session: SessionDep
) -> AttachmentOut:
    """Create a new attachment metadata record.

    Args:
        attachment: Attachment metadata supplied in the request body.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Created attachment metadata with generated storage and certification
        context fields.

    Raises:
        HTTPException: If the parent certification or linked findings are
            missing, if a finding belongs to another certification, or if the
            attachment conflicts with existing stored data.
    """
    try:
        new_attachment = post_new_attachment(attachment, session)
    except AttachmentCertificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AttachmentFindingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AttachmentFindingCertificationMismatchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AttachmentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return AttachmentOut.model_validate(new_attachment)
