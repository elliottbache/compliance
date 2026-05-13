from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    ArchiveRequest,
    AttachmentCreate,
    AttachmentOut,
    AttachmentWithContextOut,
)
from compliance.services.attachments import (
    AttachmentCertificationNotFoundError,
    AttachmentConflictError,
    AttachmentFindingCertificationMismatchError,
    AttachmentFindingNotFoundError,
    AttachmentRuleNotFoundError,
    AttachmentSiteNotFoundError,
    get_attachment_by_id,
    get_attachments,
    post_attachment_archived_by_id,
    post_attachment_restored_by_id,
    post_new_attachment,
)

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.get("")
def get_attachments_route(
    session: SessionDep,
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


@router.get("/{attachment_id}")
def get_attachment_by_id_route(
    session: SessionDep,
    attachment_id: int,
    include_archived: Annotated[bool, Query()] = True,
) -> AttachmentWithContextOut:
    """Return one attachment with certification, regulation, and finding context.

    Args:
        session: Database session provided by FastAPI dependency injection.
        attachment_id: Unique identifier for the attachment to retrieve.
        include_archived: When true, return archived attachments and related
            certification, site, regulation, finding, and rule context.

    Returns:
        Attachment details serialized with certification, regulation, and
        linked finding context.

    Raises:
        HTTPException: If no visible attachment exists for the requested ID.
    """
    result = get_attachment_by_id(
        session, attachment_id, include_archived=include_archived
    )
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Attachment {attachment_id} not found."
        )

    return AttachmentWithContextOut.model_validate(result)


@router.post("", status_code=201)
def post_new_attachment_route(
    session: SessionDep, attachment: AttachmentCreate
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
        new_attachment = post_new_attachment(session, attachment)
    except AttachmentCertificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AttachmentFindingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AttachmentFindingCertificationMismatchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AttachmentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return AttachmentOut.model_validate(new_attachment)


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
