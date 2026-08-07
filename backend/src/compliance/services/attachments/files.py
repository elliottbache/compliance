"""Attachment file upload, validation, persistence, and configured storage helpers."""

from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4

import clamd
import magic
from compliance.config import settings
from compliance.db.models import Attachment, AuditAction, AuditTargetType, Certification
from compliance.services.attachments.exceptions import (
    AttachmentCertificationNotFoundError,
    AttachmentConflictError,
    AttachmentFileError,
    AttachmentInfectedError,
    AttachmentNotFoundError,
    AttachmentPermissionError,
    AttachmentScanError,
    AttachmentScannerUnavailableError,
    AttachmentTooLargeError,
    AttachmentUnsupportedMediaTypeError,
)
from compliance.services.audit import record_audit_event
from compliance.services.schemas import UserOut
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

_UPLOAD_DIR = settings.attachments_dir
_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv"}
_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "text/plain",
    "text/csv",
}
_ALLOWED_SIZE = int(5e7)
_DANGEROUS_INNER_EXTENSIONS = {
    ".bat",
    ".cmd",
    ".com",
    ".exe",
    ".jar",
    ".js",
    ".msi",
    ".ps1",
    ".scr",
    ".sh",
    ".vbs",
}


class FileScanner(Protocol):
    def scan(self, file_stream: BinaryIO) -> None:
        """Raise an exception when the file is unsafe or cannot be scanned."""


class NoOpFileScanner:
    def scan(self, file_stream: BinaryIO) -> None:
        """Skip malware scan."""

        if not file_stream:
            raise AttachmentScanError("No file to scan.")


class ClamAVFileScanner:
    """Scan uploaded files through a ClamAV daemon on the private network."""

    def __init__(
        self,
        *,
        host: str,
        port: int = 3310,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._client = clamd.ClamdNetworkSocket(
            host=host,
            port=port,
            timeout=timeout_seconds,
        )

    def scan(self, file_stream: BinaryIO) -> None:
        """Stream a file to ClamAV, rewind it, and require a clean result."""

        try:
            result = self._client.instream(file_stream)
            file_stream.seek(0)

        except clamd.BufferTooLongError as exc:
            raise AttachmentScanError(
                "File exceeds the ClamAV stream-size limit."
            ) from exc

        except (clamd.ConnectionError, OSError) as exc:
            raise AttachmentScannerUnavailableError("ClamAV is unavailable.") from exc

        except clamd.ResponseError as exc:
            raise AttachmentScanError(
                "ClamAV returned an invalid scan response."
            ) from exc

        if not result:
            raise AttachmentScanError("ClamAV returned no scan result.")

        _, scan_result = next(iter(result.items()))
        status, reason = scan_result

        if status == "FOUND":
            raise AttachmentInfectedError(
                reason or "Malware detected in uploaded file."
            )

        if status != "OK":
            raise AttachmentScanError(reason or f"Unexpected ClamAV status: {status}")


def post_attachment_upload(
    session: Session,
    *,
    attachment_id: int,
    file_size: int | None,
    file_type: str | None,
    file_name: str | None,
    file_stream: BinaryIO,
    actor: UserOut | None = None,
    user_id: int | None = None,
) -> Attachment:
    """Persist an uploaded file for an existing attachment metadata record.

    Args:
        session: Database session used to retrieve and update attachment metadata.
        attachment_id: Primary key of the attachment metadata row to update.
        file_size: Size of the uploaded file in bytes.
        file_type: MIME type reported for the uploaded file. The content is
            also inspected before the file is stored.
        file_name: Original uploaded filename, used only to derive the extension.
        file_stream: Binary stream containing the uploaded file content.

    Returns:
        The updated attachment ORM object.

    Raises:
        AttachmentFileError: If required upload metadata is missing or invalid.
        AttachmentUnsupportedMediaTypeError: If the upload MIME type, detected
            content type, or extension is not accepted.
        AttachmentInfectedError: If ClamAV detects malware in the upload.
        AttachmentScannerUnavailableError: If malware scanning is enabled but
            ClamAV cannot be reached.
        AttachmentScanError: If ClamAV returns an invalid or unexpected scan
            response.
        AttachmentNotFoundError: If no attachment metadata row exists for the ID.
        AttachmentConflictError: If the file or database update cannot be
            persisted.
    """
    if not _validate_file_size(file_size):
        raise AttachmentFileError(
            "Attachment could not be uploaded: "
            f"{file_name} with type {file_type} and size {file_size}."
        )

    if file_type is None or file_name is None or not file_name.strip():
        raise AttachmentFileError(
            "Attachment could not be uploaded: "
            f"{file_name} with type {file_type} and size {file_size}."
        )

    if not _validate_file_type_and_ext(file_type, file_name, file_stream):
        raise AttachmentUnsupportedMediaTypeError(
            "Attachment file type or extension is not supported: "
            f"{file_name} with type {file_type}."
        )

    scanner = _build_file_scanner()
    scanner.scan(file_stream)
    current_user_id = actor.id if actor is not None else user_id

    # fetch metadata
    attachment = session.get(Attachment, attachment_id)
    if attachment is None:
        raise AttachmentNotFoundError(f"Attachment with ID {attachment_id} not found.")

    # check if certification exists
    certification = session.get(Certification, attachment.certification_id)
    if certification is None:
        raise AttachmentCertificationNotFoundError(
            f"Certification {attachment.certification_id} does not exist."
        )

    # check if certification belongs to current user
    if certification.inspector_id != current_user_id:
        raise AttachmentPermissionError(
            f"Certification {attachment.certification_id} is assigned to inspector {certification.inspector_id}.  You are logged in as inspector {current_user_id}."
        )

    # extract extension
    ext = Path(file_name).suffix if file_name is not None else ""

    # create file name
    unique_filename = f"{uuid4()}{ext}"

    # set file path
    file_path = _UPLOAD_DIR / unique_filename

    try:
        # stream to path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        _copy_upload_with_limit(file_stream, file_path, _ALLOWED_SIZE)

        attachment.file_path = str(file_path)
        attachment.uploaded_at = datetime.now(UTC)

        session.add(attachment)
        if actor is not None:
            record_audit_event(
                session,
                action=AuditAction.ATTACHMENT_UPLOADED,
                target_type=AuditTargetType.ATTACHMENT,
                target_id=attachment.id,
                actor_user_id=actor.id,
                actor_email=actor.email,
                context={
                    "attachment_id": attachment.id,
                    "certification_id": attachment.certification_id,
                    "filename": file_name,
                    "content_type": file_type,
                    "file_size": file_size,
                },
            )
        session.commit()
        session.refresh(attachment)

    except AttachmentTooLargeError as e:
        session.rollback()
        file_path.unlink(missing_ok=True)
        raise AttachmentTooLargeError(
            f"File persistence error for file: {file_name}."
        ) from e

    except (OSError, SQLAlchemyError) as e:
        session.rollback()
        file_path.unlink(missing_ok=True)
        raise AttachmentConflictError(
            f"File persistence error for file: {file_name}."
        ) from e

    except Exception:
        session.rollback()
        file_path.unlink(missing_ok=True)
        raise

    return attachment


def get_attachment_download(
    session: Session, attachment_id: int, *, actor: UserOut | None = None
) -> tuple[str, Path]:
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
        raise AttachmentNotFoundError(f"Attachment with ID {attachment_id} not found.")

    if not attachment.file_path:
        raise AttachmentFileError(
            f"Attachment file does not exist or not found: {attachment.file_path}."
        )

    file_path = Path(attachment.file_path)
    if not file_path.is_file():
        raise AttachmentFileError(
            f"Attachment file does not exist or not found: {attachment.file_path}."
        )

    file_name = (
        Path(attachment.file_name).name
        if attachment.file_name and attachment.file_name.strip()
        else f"attachment_{attachment.id}"
    )
    file_name += str(file_path.suffix)

    if actor is not None:
        record_audit_event(
            session,
            action=AuditAction.ATTACHMENT_DOWNLOADED,
            target_type=AuditTargetType.ATTACHMENT,
            target_id=attachment.id,
            actor_user_id=actor.id,
            actor_email=actor.email,
            context={
                "attachment_id": attachment.id,
                "certification_id": attachment.certification_id,
                "filename": file_name,
            },
        )
        session.commit()

    return file_name, file_path


def check_attachment_storage() -> bool:
    """Return whether configured attachment storage exists and accepts writes."""
    try:
        if not _UPLOAD_DIR.is_dir():
            return False

        test_file = _UPLOAD_DIR / ".healthcheck.tmp"
        test_file.write_bytes(b"ok")
        test_file.unlink()

        return True

    except OSError:
        return False


def _build_file_scanner() -> FileScanner:
    if not settings.malware_scanning_enabled:
        return NoOpFileScanner()

    return ClamAVFileScanner(
        host=settings.malware_scanner_host,
        port=settings.malware_scanner_port,
    )


def _copy_upload_with_limit(
    source: BinaryIO, destination: Path, max_bytes: int, chunk_size: int = 1024 * 1024
) -> int:
    total = 0

    try:
        with destination.open("xb") as output:
            while chunk := source.read(chunk_size):
                total += len(chunk)

                if total > max_bytes:
                    raise AttachmentTooLargeError

                output.write(chunk)

        return total

    except Exception:
        destination.unlink(missing_ok=True)
        raise


def _validate_file_size_type_and_ext(
    file_size: int | None,
    file_type: str | None,
    file_name: str | None,
    file_stream: BinaryIO,
    *,
    allowed_size: int = _ALLOWED_SIZE,
    allowed_types: set[str] = _ALLOWED_MIME_TYPES,
    allowed_extensions: set[str] = _ALLOWED_EXTENSIONS,
) -> bool:
    """Return whether uploaded file metadata and content satisfy upload policy."""

    if not _validate_file_size(file_size, allowed_size=allowed_size):
        return False

    return _validate_file_type_and_ext(
        file_type,
        file_name,
        file_stream,
        allowed_types=allowed_types,
        allowed_extensions=allowed_extensions,
    )


def _validate_file_size(
    file_size: int | None,
    *,
    allowed_size: int = _ALLOWED_SIZE,
) -> bool:
    """Return whether an uploaded file size is present and within policy."""

    return bool(file_size) and (file_size or 0) <= allowed_size


def _validate_file_type_and_ext(
    file_type: str | None,
    file_name: str | None,
    file_stream: BinaryIO,
    *,
    allowed_types: set[str] = _ALLOWED_MIME_TYPES,
    allowed_extensions: set[str] = _ALLOWED_EXTENSIONS,
) -> bool:
    """Return whether uploaded file type, detected content, and extension match policy."""

    if file_type is None or file_type not in allowed_types:
        return False

    if file_name is None:
        return False

    header_bytes = file_stream.read(2048)
    file_stream.seek(0)

    mime_type = magic.from_buffer(header_bytes, mime=True)
    if mime_type is None or mime_type not in allowed_types:
        return False

    normalized_name = Path(file_name.strip()).name
    if not normalized_name:
        return False

    suffixes = [suffix.lower() for suffix in Path(normalized_name).suffixes]
    if not suffixes or suffixes[-1] not in allowed_extensions:
        return False

    return not any(suffix in _DANGEROUS_INNER_EXTENSIONS for suffix in suffixes[:-1])
