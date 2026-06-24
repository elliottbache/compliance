"""Attachment service exception hierarchy."""


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
