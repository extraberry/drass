"""File storage helpers: layout, safe paths, atomic placement, integrity check."""
import mimetypes
import os
from pathlib import Path
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from ..core.config import get_settings
from ..domain.enums import FileType
from ..domain.errors import NotFound, StorageError
from ..domain.file_validation import safe_join, sha256_file
from ..models import FileRecord


def subdir(file_type: FileType) -> str:
    return "manuscripts" if file_type is FileType.MANUSCRIPT else "companions"


def ensure_dirs() -> None:
    for d in ("manuscripts", "companions", "temp"):
        (get_settings().storage_root / d).mkdir(parents=True, exist_ok=True)


def temp_path() -> Path:
    import uuid
    return get_settings().storage_root / "temp" / f"{uuid.uuid4().hex}.part"


def dest_path(file_type: FileType, stored_name: str) -> str:
    return safe_join(str(get_settings().storage_root / subdir(file_type)), stored_name)


def add_record(db: Session, work_id: int, revision_id, file_type: FileType, original: str, stored: str,
               size: int, sha: str, uploader_id: int) -> tuple[FileRecord, bool]:
    """Deactivate previous active file of the same type (single-file types) and insert the new one."""
    replaced = False
    if file_type is not FileType.OTHER_COMPANION:
        res = db.execute(update(FileRecord).where(FileRecord.work_id == work_id,
                                                  FileRecord.file_type == file_type.value,
                                                  FileRecord.is_active.is_(True)).values(is_active=False))
        replaced = bool(res.rowcount)
    mime = "application/pdf" if file_type is FileType.MANUSCRIPT else (mimetypes.guess_type(original)[0] or "application/octet-stream")
    rec = FileRecord(work_id=work_id, revision_id=revision_id, file_type=file_type.value,
                     original_filename=original, stored_filename=stored,
                     storage_path=f"{subdir(file_type)}/{stored}", mime_type=mime, size_bytes=size,
                     sha256_checksum=sha, uploaded_by=uploader_id, is_active=True)
    db.add(rec)
    db.flush()
    return rec, replaced


def active_manuscript(db: Session, work_id: int) -> FileRecord | None:
    return db.scalar(select(FileRecord).where(FileRecord.work_id == work_id,
                                              FileRecord.file_type == "MANUSCRIPT",
                                              FileRecord.is_active.is_(True)))


def manuscript_path(db: Session, work_id: int) -> str:
    rec = active_manuscript(db, work_id)
    if rec is None:
        raise NotFound("No manuscript is available for this research.")
    path = safe_join(str(get_settings().storage_root / "manuscripts"), rec.stored_filename)
    if not os.path.exists(path):
        raise StorageError("The manuscript file could not be found on the server.")
    return path


def verify_manuscript_integrity(db: Session, work_id: int) -> None:
    rec = active_manuscript(db, work_id)
    if rec is None:
        raise StorageError("Cannot archive: no manuscript is attached.")
    path = manuscript_path(db, work_id)
    if sha256_file(path) != rec.sha256_checksum:
        raise StorageError("Cannot archive: manuscript checksum mismatch.")
