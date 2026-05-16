import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from compliance.db.models import Attachment
from compliance.services.attachments.crud import (
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
