from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
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
        include_archived: When true, include archived attachments.

    Returns:
        Attachment records serialized with certification, regulation, and linked
        finding ID context.

    Raises:
        HTTPException: If a requested site, certification, rule, or finding
            filter references a missing record.
    """
    try:
        attachments = get_attachments(
            session,
            site_id,
            certification_id,
            rule_id,
            finding_id,
            include_archived,
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
    attachment_id: int,
    session: SessionDep,
    include_archived: Annotated[bool, Query()] = False,
) -> AttachmentWithContextOut:
    """Return one attachment with certification, regulation, and finding context.

    Args:
        attachment_id: Unique identifier for the attachment to retrieve.
        session: Database session provided by FastAPI dependency injection.
        include_archived: When true, return archived attachments.

    Returns:
        Attachment details serialized with certification, regulation, and
        linked finding context.

    Raises:
        HTTPException: If no attachment exists for the requested ID.
    """
    result = get_attachment_by_id(attachment_id, session, include_archived)
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
