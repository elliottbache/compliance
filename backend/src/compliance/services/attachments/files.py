import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from compliance.db.models import Attachment
from compliance.services.attachments import (
    AttachmentConflictError,
    AttachmentFileError,
    AttachmentNotFoundError,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

_PROJECT_ROOT = Path(__file__).resolve().parents[5]
_UPLOAD_DIR = _PROJECT_ROOT / "backend" / "storage" / "attachments"
_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv"}
_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "text/plain",
    "text/csv",
}
_ALLOWED_SIZE = int(5e7)


def get_attachment_download(session: Session, attachment_id: int) -> tuple[str, Path]:
    """Return the download name and stored file path for an attachment.

    Args:
        session: Database session used to retrieve the attachment metadata.
        attachment_id: Primary key of the attachment to download.

    Returns:
        The browser-facing filename and the stored filesystem path.

    Raises:
        AttachmentNotFoundError: If no attachment exists for the supplied ID.
        AttachmentFileError: If the attachment has no stored path or the file is
            missing from disk.
    """
    attachment = session.get(Attachment, attachment_id)
    if not attachment:
        raise AttachmentNotFoundError(attachment_id)

    if not attachment.file_path:
        raise AttachmentFileError(attachment_id, attachment.file_path)

    file_path = Path(attachment.file_path)
    if not file_path.is_file():
        raise AttachmentFileError(attachment_id, attachment.file_path)

    file_name = attachment.file_name or ""
    file_name += str(file_path.suffix)

    return file_name, file_path


def post_attachment_upload(
    session: Session,
    *,
    attachment_id: int,
    file_size: int | None,
    file_type: str | None,
    file_name: str | None,
    file_stream: BinaryIO,
) -> Attachment:
    """Persist an uploaded file for an existing attachment metadata record.

    Args:
        session: Database session used to retrieve and update attachment metadata.
        attachment_id: Primary key of the attachment metadata row to update.
        file_size: Size of the uploaded file in bytes.
        file_type: MIME type reported for the uploaded file.
        file_name: Original uploaded filename, used only to derive the extension.
        file_stream: Binary stream containing the uploaded file content.

    Returns:
        The updated attachment ORM object.

    Raises:
        AttachmentFileError: If the upload size, MIME type, or extension is not
            accepted.
        AttachmentNotFoundError: If no attachment metadata row exists for the ID.
        AttachmentConflictError: If the file or database update cannot be
            persisted.
    """
    # check that content type and extension is acceptable
    if not _validate_file_size_type_and_ext(file_size, file_type, file_name):
        raise AttachmentFileError(file_size, file_type, file_name)

    # fetch metadata
    attachment = session.get(Attachment, attachment_id)
    if attachment is None:
        raise AttachmentNotFoundError(attachment_id)

    # extract extension
    ext = Path(file_name).suffix if file_name is not None else ""

    # create file name
    unique_filename = f"{uuid4()}{ext}"

    # set file path
    file_path = _UPLOAD_DIR / unique_filename

    try:
        # stream to path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file_stream, buffer)

        attachment.file_path = str(file_path)
        attachment.uploaded_at = datetime.now(UTC)

        session.add(attachment)
        session.commit()
        session.refresh(attachment)

    except (OSError, SQLAlchemyError) as e:
        session.rollback()
        file_path.unlink(missing_ok=True)
        raise AttachmentConflictError(file_path) from e

    except Exception:
        session.rollback()
        file_path.unlink(missing_ok=True)
        raise

    return attachment


def _validate_file_size_type_and_ext(
    file_size: int | None,
    file_type: str | None,
    file_name: str | None,
    *,
    allowed_size: int = _ALLOWED_SIZE,
    allowed_types: set[str] = _ALLOWED_MIME_TYPES,
    allowed_extensions: set[str] = _ALLOWED_EXTENSIONS,
) -> bool:

    if not file_size or file_size > allowed_size:
        return False

    if file_type is None or file_type not in allowed_types:
        return False

    return file_name is None or Path(file_name).suffix in allowed_extensions
