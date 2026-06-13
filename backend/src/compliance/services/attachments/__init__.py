class AttachmentCreateError(Exception):
    """Base error for attachment service failures."""


class AttachmentNotFoundError(AttachmentCreateError):
    """Raised when an attachment ID does not exist."""


class AttachmentPermissionError(AttachmentCreateError):
    """Raised when an attachment belongs to a different inspector."""


class AttachmentSiteNotFoundError(AttachmentCreateError):
    """Raised when an attachment filter references a missing site."""


class AttachmentCertificationNotFoundError(AttachmentCreateError):
    """Raised when an attachment's certification does not exist."""


class AttachmentRuleNotFoundError(AttachmentCreateError):
    """Raised when an attachment filter references a missing rule."""


class AttachmentFindingNotFoundError(AttachmentCreateError):
    """Raised when an attachment's linked finding does not exist."""


class AttachmentFindingCertificationMismatchError(AttachmentCreateError):
    """Raised when a linked finding belongs to another certification."""


class AttachmentConflictError(AttachmentCreateError):
    """Raised when attachment creation conflicts with stored data."""


class AttachmentFileError(AttachmentCreateError):
    """Raised when attachment file upload or download is invalid."""


from compliance.services.attachments.crud import (  # noqa: E402
    get_attachment_by_id,
    get_attachments,
    post_attachment_archived_by_id,
    post_attachment_restored_by_id,
    post_new_attachment,
)
from compliance.services.attachments.files import (  # noqa: E402
    _UPLOAD_DIR,
    _validate_file_size_type_and_ext,
    get_attachment_download,
    post_attachment_upload,
)
from compliance.services.attachments.formatting import (  # noqa: E402
    _build_attachment_out,
    _build_finding_history_from_site_attachments,
    _format_attachments,
    _format_new_attachment_with_context,
    format_attachment,
)

__all__ = [
    "_UPLOAD_DIR",
    "AttachmentCertificationNotFoundError",
    "AttachmentConflictError",
    "AttachmentCreateError",
    "AttachmentFileError",
    "AttachmentFindingCertificationMismatchError",
    "AttachmentFindingNotFoundError",
    "AttachmentNotFoundError",
    "AttachmentRuleNotFoundError",
    "AttachmentSiteNotFoundError",
    "_build_attachment_out",
    "_build_finding_history_from_site_attachments",
    "_format_attachments",
    "_format_new_attachment_with_context",
    "_validate_file_size_type_and_ext",
    "format_attachment",
    "get_attachment_by_id",
    "get_attachment_download",
    "get_attachments",
    "post_attachment_archived_by_id",
    "post_attachment_restored_by_id",
    "post_attachment_upload",
    "post_new_attachment",
]
