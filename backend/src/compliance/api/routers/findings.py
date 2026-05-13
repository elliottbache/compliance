from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    ArchiveRequest,
    FindingCreate,
    FindingOut,
)
from compliance.services.findings import (
    FindingAttachmentCertificationMismatchError,
    FindingConflictError,
    FindingMissingAttachmentError,
    FindingMissingCertificationError,
    FindingMissingRuleError,
    FindingMissingSiteError,
    get_finding_by_id,
    get_findings,
    post_finding_archived_by_id,
    post_finding_restored_by_id,
    post_new_finding,
)

router = APIRouter(prefix="/findings", tags=["findings"])


@router.get("")
def get_findings_route(
    session: SessionDep,
    site_id: Annotated[int | None, Query(gt=0)] = None,
    certification_id: Annotated[int | None, Query(gt=0)] = None,
    rule_id: Annotated[int | None, Query(gt=0)] = None,
    attachment_id: Annotated[int | None, Query(gt=0)] = None,
    open_only: Annotated[bool, Query()] = False,
    include_archived: Annotated[bool, Query()] = False,
) -> list[FindingOut]:
    """Return findings with optional filters.

    Args:
        session: Database session provided by FastAPI dependency injection.
        site_id: Optional site identifier used to limit findings to one site.
        certification_id: Optional certification identifier used to limit findings
            to one certification.
        rule_id: Optional rule identifier used to limit findings to one rule.
        attachment_id: Optional attachment identifier used to limit findings to one
            attachment.
        open_only: When true, only return findings whose certification has no
            resolution date.
        include_archived: When true, include archived findings and related
            certification, site, regulation, rule, and attachment context. By
            default, archived optional attachment links are omitted without
            hiding otherwise visible findings.

    Returns:
        Finding records serialized with certification, regulation, rule, and
        linked attachment context.

    Raises:
        HTTPException: If a requested site, certification, rule, or attachment
            filter references a missing visible record.
    """
    try:
        findings = get_findings(
            session,
            site_id=site_id,
            certification_id=certification_id,
            rule_id=rule_id,
            attachment_id=attachment_id,
            open_only=open_only,
            include_archived=include_archived,
        )
    except FindingMissingSiteError as err:
        raise HTTPException(status_code=404, detail=f"Missing site {site_id}.") from err
    except FindingMissingCertificationError as err:
        raise HTTPException(
            status_code=404, detail=f"Missing certification {certification_id}."
        ) from err
    except FindingMissingRuleError as err:
        raise HTTPException(status_code=404, detail=f"Missing rule {rule_id}.") from err
    except FindingMissingAttachmentError as err:
        raise HTTPException(
            status_code=404, detail=f"Missing attachment {attachment_id}."
        ) from err

    return findings


@router.get("/{finding_id}")
def get_finding_by_id_route(
    session: SessionDep,
    finding_id: int,
    include_archived: Annotated[bool, Query()] = True,
) -> FindingOut:
    """Return one finding by ID.

    Args:
        session: Database session provided by FastAPI dependency injection.
        finding_id: Unique identifier for the finding to retrieve.
        include_archived: When true, return archived findings and related
            certification, site, regulation, rule, and attachment context.

    Returns:
        Finding details serialized with certification, regulation, rule, and
        linked attachment context.

    Raises:
        HTTPException: If no visible finding exists for the requested ID.
    """
    finding = get_finding_by_id(session, finding_id, include_archived=include_archived)
    if finding is None:
        raise HTTPException(
            status_code=404,
            detail=f"No finding for this id found: {finding_id}",
        )

    return finding


@router.post("", status_code=201)
def post_new_finding_route(session: SessionDep, finding: FindingCreate) -> FindingOut:
    """Create a new finding record.

    Args:
        session: Database session provided by FastAPI dependency injection.
        finding: Finding details supplied in the request body.

    Returns:
        Created finding details serialized with the public API response schema.

    Raises:
        HTTPException: If the finding references missing certification, rule, or
            attachment data, links an attachment from another certification, or
            another integrity conflict prevents creation.
    """
    try:
        new_finding = post_new_finding(session, finding)

    except FindingAttachmentCertificationMismatchError as err:
        raise HTTPException(
            status_code=422,
            detail=str(err),
        ) from err

    except FindingMissingCertificationError as err:
        raise HTTPException(
            status_code=404,
            detail=f"Certification {finding.certification_id} does not exist.",
        ) from err

    except FindingMissingRuleError as err:
        raise HTTPException(
            status_code=404,
            detail=f"Rule {finding.rule_id} does not exist.",
        ) from err

    except FindingMissingAttachmentError as err:
        raise HTTPException(
            status_code=404,
            detail=str(err),
        ) from err

    except FindingConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=f"Finding was not added: {finding}.",
        ) from err

    return FindingOut.model_validate(new_finding)


@router.post("/{finding_id}/archive", status_code=200)
def post_finding_archived_by_id_route(
    session: SessionDep,
    finding_id: Annotated[int, Path(ge=1)],
    archive_request: ArchiveRequest | None = None,
) -> FindingOut:
    """Archive one finding by ID."""
    archive_request = archive_request or ArchiveRequest()

    finding = post_finding_archived_by_id(
        session, finding_id, archive_request=archive_request
    )
    if finding is None:
        raise HTTPException(
            status_code=404, detail=f"Finding does not exist: {finding_id}."
        )

    return FindingOut.model_validate(finding)


@router.post("/{finding_id}/restore", status_code=200)
def post_finding_restored_by_id_route(
    session: SessionDep, finding_id: Annotated[int, Path(ge=1)]
) -> FindingOut:
    """Restore one archived finding by ID."""
    finding = post_finding_restored_by_id(session, finding_id)
    if finding is None:
        raise HTTPException(
            status_code=404, detail=f"Finding does not exist: {finding_id}."
        )

    return FindingOut.model_validate(finding)
