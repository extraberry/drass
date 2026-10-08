"""Secure reader: server renders single pages to PNG; the client never receives the PDF (PRD s26-27)."""
from sqlalchemy.orm import Session
from ..domain.errors import NotFound, StorageError, ValidationFailed
from ..models import User
from . import files_service
from .common import activity
from .repository_service import get_work_for_user


def _open(path: str):
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:   # pragma: no cover
        raise StorageError("PDF rendering library (PyMuPDF) is not installed on the server.") from exc
    try:
        return fitz.open(path)
    except Exception as exc:   # noqa: BLE001
        raise StorageError("The manuscript could not be opened. It may be corrupted.") from exc


def info(db: Session, user: User, work_id: int) -> dict:
    get_work_for_user(db, user, work_id)
    doc = _open(files_service.manuscript_path(db, work_id))
    try:
        return {"work_id": work_id, "page_count": doc.page_count}
    finally:
        doc.close()


def render_page(db: Session, user: User, work_id: int, page: int, scale: float) -> tuple[bytes, dict]:
    get_work_for_user(db, user, work_id)
    if not (0.4 <= scale <= 4.0):
        raise ValidationFailed("Invalid zoom level.")
    doc = _open(files_service.manuscript_path(db, work_id))
    try:
        if page < 1 or page > doc.page_count:
            raise NotFound("Page not found.")
        import fitz
        p = doc.load_page(page - 1)
        pix = p.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        png = pix.tobytes("png")
        meta = {"page_count": doc.page_count, "page_width": p.rect.width, "page_height": p.rect.height}
    finally:
        doc.close()
    activity(db, user.user_id, "PDF_PAGE_VIEWED", "work", work_id, f"page {page}")
    db.commit()
    return png, meta
