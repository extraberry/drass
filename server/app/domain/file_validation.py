"""Upload validation: size, signature, name sanitising, checksum (PRD s9-10)."""
import hashlib
import os
import re
import uuid
from .enums import FileType
from .errors import ValidationFailed

MB = 1024 * 1024
DEFAULT_LIMITS_MB = {FileType.MANUSCRIPT: 100, FileType.SOURCE_CODE: 500,
                     FileType.VIDEO: 500, FileType.OTHER_COMPANION: 500}
ALLOWED_EXT = {
    FileType.MANUSCRIPT: {".pdf"},
    FileType.SOURCE_CODE: {".zip", ".7z", ".rar"},
    FileType.VIDEO: {".mp4", ".mov", ".webm"},
    FileType.OTHER_COMPANION: {".zip", ".7z", ".rar", ".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".png", ".jpg"},
}


def _signature_ok(ext: str, head: bytes) -> bool:
    if ext in (".docx", ".pptx", ".xlsx"):
        return head[:2] == b"PK"
    if ext == ".png":
        return head[:8] == b"\x89PNG\r\n\x1a\n"
    if ext == ".jpg":
        return head[:3] == b"\xff\xd8\xff"
    if ext == ".txt":
        return b"\x00" not in head
    if ext == ".pdf":
        return head.lstrip(b"\x00 \t\r\n")[:5] == b"%PDF-"
    if ext == ".zip":
        return head[:4] in (b"PK\x03\x04", b"PK\x05\x06")
    if ext == ".7z":
        return head[:6] == b"7z\xbc\xaf\x27\x1c"
    if ext == ".rar":
        return head[:7] == b"Rar!\x1a\x07\x00" or head[:8] == b"Rar!\x1a\x07\x01\x00"
    if ext in (".mp4", ".mov"):
        return head[4:8] == b"ftyp" or head[4:8] in (b"moov", b"mdat", b"wide", b"free")
    if ext == ".webm":
        return head[:4] == b"\x1a\x45\xdf\xa3"
    return False


def validate_upload(file_type: FileType, filename: str, head: bytes, size: int,
                    limits_mb: dict | None = None) -> str:
    """Return the lowercase extension if valid, else raise ValidationFailed."""
    limits = {**DEFAULT_LIMITS_MB, **(limits_mb or {})}
    ext = os.path.splitext(filename or "")[1].lower()
    allowed = ALLOWED_EXT.get(file_type)
    if allowed is not None and ext not in allowed:
        raise ValidationFailed(f"Invalid file type. Allowed: {', '.join(sorted(allowed))}.")
    if size <= 0:
        raise ValidationFailed("The file is empty.")
    if size > limits[file_type] * MB:
        raise ValidationFailed(f"File exceeds the {limits[file_type]} MB limit.")
    if allowed is not None and not _signature_ok(ext, head):
        raise ValidationFailed("File content does not match its extension.")
    return ext


def sanitize_filename(name: str) -> str:
    base = os.path.basename((name or "").replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(". ")
    return base[:150] or "file"


def new_stored_name(ext: str) -> str:
    return f"{uuid.uuid4().hex}{ext}"


def safe_join(root: str, stored_name: str) -> str:
    """Resolve inside root or raise (path-traversal guard)."""
    root_abs = os.path.realpath(root)
    path = os.path.realpath(os.path.join(root_abs, stored_name))
    if os.path.commonpath([root_abs, path]) != root_abs or path == root_abs:
        raise ValidationFailed("Invalid file path.")
    return path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
