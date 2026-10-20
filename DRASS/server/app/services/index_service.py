"""Embedding pipeline for ARCHIVED works only (title + abstract + keywords) — PRD s18-19, s72-73."""
import logging
import threading
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..core.timeutil import utcnow
from ..domain import search_core as sc
from ..models import Embedding, ResearchWork
from .common import audit, notify_roles
from .embedder import get_embedder
from .serializers import keywords_of

log = logging.getLogger("drass.indexing")
PROGRESS = {"running": False, "done": 0, "total": 0, "failed": 0}
_plock = threading.Lock()


def index_text_for(db: Session, w: ResearchWork) -> str:
    return sc.build_index_text(w.title, w.abstract, keywords_of(db, w.work_id))


def _row(db: Session, work_id: int) -> Embedding:
    row = db.scalar(select(Embedding).where(Embedding.work_id == work_id))
    if row is None:
        row = Embedding(work_id=work_id, status="PENDING")
        db.add(row)
    return row


def index_work(db: Session, work_id: int, actor_id=None, rebuilt: bool = False) -> bool:
    """Never raises; archiving must not fail because indexing failed. Commits its own work."""
    w = db.get(ResearchWork, work_id)
    if w is None or w.current_status != "ARCHIVED":
        return False
    try:
        text = index_text_for(db, w)
        emb = get_embedder()
        vec = emb.encode([text])[0]
        row = _row(db, work_id)
        row.model_name, row.dimension, row.dtype = emb.model_name, int(vec.shape[0]), "float32"
        row.vector_blob, row.indexed_text_hash = sc.to_blob(vec), sc.text_hash(text)
        row.status, row.error_message, row.indexed_at = "COMPLETE", None, utcnow()
        audit(db, actor_id, "EMBEDDING_REBUILT" if rebuilt else "EMBEDDING_CREATED", "work", work_id)
        db.commit()
        return True
    except Exception as exc:   # noqa: BLE001 - failure is recorded, not propagated
        db.rollback()
        log.exception("indexing failed for work %s", work_id)
        row = _row(db, work_id)
        row.status, row.error_message = "FAILED", str(exc)[:480]
        audit(db, actor_id, "EMBEDDING_FAILED", "work", work_id, "FAILED", str(exc)[:500])
        notify_roles(db, ["ADMIN", "HEAD_LIBRARIAN"], "Indexing failure",
                     f"Semantic indexing failed for work #{work_id}. Retry from the Indexing Monitor.",
                     "INDEXING", "work", work_id)
        db.commit()
        return False


def mark_stale(db: Session, work_id: int) -> None:
    row = db.scalar(select(Embedding).where(Embedding.work_id == work_id))
    if row is not None:
        row.status = "STALE"


def stats(db: Session) -> dict:
    archived = db.scalar(select(func.count()).select_from(ResearchWork).where(ResearchWork.current_status == "ARCHIVED")) or 0
    by = dict(db.execute(select(Embedding.status, func.count()).group_by(Embedding.status)).all())
    complete, failed = by.get("COMPLETE", 0), by.get("FAILED", 0)
    last = db.scalar(select(func.max(Embedding.indexed_at)))
    model = db.scalar(select(Embedding.model_name).where(Embedding.status == "COMPLETE").limit(1))
    return {"total_archived": archived, "indexed": complete, "failed": failed, "stale": by.get("STALE", 0),
            "pending": max(archived - complete - failed - by.get("STALE", 0), 0),
            "model": model, "last_indexed_at": last.isoformat() if last else None, "progress": dict(PROGRESS)}


def failures(db: Session) -> list[dict]:
    rows = db.execute(select(Embedding, ResearchWork.title).join(ResearchWork, ResearchWork.work_id == Embedding.work_id)
                      .where(Embedding.status.in_(["FAILED", "STALE"]))).all()
    return [{"work_id": e.work_id, "title": t, "status": e.status, "error": e.error_message} for e, t in rows]


def rebuild(session_factory, mode: str, actor_id: int) -> None:
    """Background task: own DB session; progress exposed via PROGRESS."""
    with _plock:
        if PROGRESS["running"]:
            return
        PROGRESS.update(running=True, done=0, total=0, failed=0)
    db = session_factory()
    try:
        archived = select(ResearchWork.work_id).where(ResearchWork.current_status == "ARCHIVED")
        ids = list(db.scalars(archived).all())
        if mode == "failed":
            ok = set(db.scalars(select(Embedding.work_id).where(Embedding.status == "COMPLETE")).all())
            ids = [i for i in ids if i not in ok]
        PROGRESS["total"] = len(ids)
        for wid in ids:
            if not index_work(db, wid, actor_id, rebuilt=True):
                PROGRESS["failed"] += 1
            PROGRESS["done"] += 1
    finally:
        db.close()
        PROGRESS["running"] = False
