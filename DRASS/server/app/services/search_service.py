"""Semantic search + recommendations over ARCHIVED, accessible records only (PRD s17-25, s60-62)."""
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..domain import search_core as sc
from ..domain.errors import NotFound
from ..models import Embedding, ResearchKeyword, Keyword, ResearchWork, User
from .common import activity, get_setting
from .embedder import get_embedder
from .repository_service import apply_filters, get_work_for_user
from .serializers import authors_of, keywords_of, work_dict

NO_MATCH = "No sufficiently related research was found."
NO_MATCH_HINT = "Try removing filters or browsing the repository."
NO_RECS = "No closely related studies were found yet."


def _candidates(db: Session, filters: dict | None = None) -> list[sc.Candidate]:
    stmt = select(ResearchWork).where(ResearchWork.current_status == "ARCHIVED")
    if filters:
        stmt = apply_filters(stmt, filters)
    works = {w.work_id: w for w in db.scalars(stmt).all()}
    if not works:
        return []
    embs = db.scalars(select(Embedding).where(Embedding.work_id.in_(works.keys()),
                                              Embedding.status == "COMPLETE")).all()
    kw = {}
    for wid, text in db.execute(select(ResearchKeyword.work_id, Keyword.keyword_text)
                                .join(Keyword, Keyword.keyword_id == ResearchKeyword.keyword_id)
                                .where(ResearchKeyword.work_id.in_(works.keys()))).all():
        kw.setdefault(wid, set()).add(text)
    out = []
    for e in embs:
        w = works[e.work_id]
        out.append(sc.Candidate(w.work_id, sc.from_blob(e.vector_blob), w.year or 0, w.program_id,
                                w.department_id, w.category_id, frozenset(kw.get(w.work_id, ()))))
    return out


def semantic_search(db: Session, user: User, query: str, filters: dict, limit: int) -> dict:
    q = sc.normalize_query(query)
    threshold = get_setting(db, "semantic_threshold")
    qvec = get_embedder().encode([q])[0]
    cands = _candidates(db, {k: v for k, v in filters.items() if v not in (None, "")})
    ranked = sc.rank(qvec, cands, threshold, limit)
    results = []
    for wid, score in ranked:
        d = work_dict(db, db.get(ResearchWork, wid), detail=False)
        d["abstract_snippet"] = (db.get(ResearchWork, wid).abstract or "")[:280]
        d["score"] = round(score, 4)
        d["score_label"] = sc.percent(score)
        results.append(d)
    if get_setting(db, "log_search_queries"):
        activity(db, user.user_id, "SEARCH_QUERY", "search", None, q[:200])
    db.commit()
    return {"query": q, "count": len(results), "threshold": threshold, "results": results,
            "message": None if results else NO_MATCH, "hint": None if results else NO_MATCH_HINT,
            "disclaimer": "Semantic relevance is a similarity estimate, not a guarantee of factual relevance."}


def recommendations(db: Session, user: User, work_id: int) -> dict:
    w = get_work_for_user(db, user, work_id)
    count = get_setting(db, "recommendation_count")
    threshold = get_setting(db, "semantic_threshold")
    emb = db.scalar(select(Embedding).where(Embedding.work_id == work_id, Embedding.status == "COMPLETE"))
    items = []
    if emb is not None and w.current_status == "ARCHIVED":
        pool = _candidates(db)
        me = next((c for c in pool if c.work_id == work_id), None)
        if me is None:
            me = sc.Candidate(work_id, sc.from_blob(emb.vector_blob), w.year or 0, w.program_id,
                              w.department_id, w.category_id, frozenset(keywords_of(db, work_id)))
        for wid, score in sc.recommend(me, pool, threshold, count):
            d = work_dict(db, db.get(ResearchWork, wid), detail=False)
            d["score"], d["score_label"] = round(score, 4), sc.percent(score)
            items.append(d)
    activity(db, user.user_id, "RECOMMENDATIONS_VIEWED", "work", work_id)
    db.commit()
    return {"work_id": work_id, "items": items, "message": None if items else NO_RECS}
