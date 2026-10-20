"""Unauthenticated endpoints (guest browse/search, student sign-up) + roster administration."""
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..core import ratelimit
from ..core.deps import require
from ..db import get_db
from ..domain.errors import Forbidden, NotFound
from ..models import User
from ..schemas.schemas import RosterImportIn, RosterIn, SemanticSearchIn, StudentRegisterIn
from ..services import admin_service, registration_service, repository_service, search_service
from ..services.common import activity
from ..services.guest import GUEST
from ..services.serializers import work_dict

router = APIRouter()


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/public/lookups")
def public_lookups(request: Request, db: Session = Depends(get_db)):
    ratelimit.check("pub-lookups:" + _ip(request), 120, 60)
    advisers = db.scalars(select(User).where(User.status == "ACTIVE", User.role.has(role_name="ADVISER"))).all()
    return {"departments": admin_service.lookup_rows(db, "departments"), "programs": admin_service.lookup_rows(db, "programs"),
            "categories": admin_service.lookup_rows(db, "categories"),
            "advisers": [{"id": a.user_id, "name": a.full_name, "department_id": a.department_id} for a in advisers]}


@router.get("/public/repository")
def public_repository(request: Request, program_id: Optional[int] = None, department_id: Optional[int] = None,
                      year: Optional[int] = None, adviser_id: Optional[int] = None, category_id: Optional[int] = None,
                      author: Optional[str] = Query(None, max_length=200), keyword: Optional[str] = Query(None, max_length=80),
                      sort: str = "archived_at", order: str = "desc", page: int = 1, page_size: int = 20,
                      db: Session = Depends(get_db)):
    ratelimit.check("pub-repo:" + _ip(request), 120, 60)
    f = {"program_id": program_id, "department_id": department_id, "year": year, "adviser_id": adviser_id,
         "category_id": category_id, "author": author, "keyword": keyword}
    return repository_service.list_repository(db, GUEST, f, sort, order, page, page_size, None)


@router.get("/public/repository/{work_id}")
def public_detail(work_id: int, request: Request, db: Session = Depends(get_db)):
    ratelimit.check("pub-detail:" + _ip(request), 120, 60)
    try:
        w = repository_service.get_work_for_user(db, GUEST, work_id, audit_denial=False)
    except (Forbidden, NotFound):
        raise NotFound("Research not found.")          # never reveal that a non-public record exists
    activity(db, None, "RESEARCH_VIEWED", "work", work_id, "guest")
    db.commit()
    d = work_dict(db, w)
    d["can_read"] = False                               # manuscripts require sign-in
    d.pop("files", None)
    return d


@router.post("/public/search/semantic")
def public_search(body: SemanticSearchIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.check("pub-search:" + _ip(request), 30, 60)
    return search_service.semantic_search(db, GUEST, body.query, body.filters.model_dump(), body.limit)


@router.get("/public/recommendations/{work_id}")
def public_recs(work_id: int, request: Request, db: Session = Depends(get_db)):
    ratelimit.check("pub-recs:" + _ip(request), 60, 60)
    try:
        return search_service.recommendations(db, GUEST, work_id)
    except (Forbidden, NotFound):
        raise NotFound("Research not found.")


@router.post("/auth/register-student")
def register_student(body: StudentRegisterIn, request: Request, db: Session = Depends(get_db)):
    ratelimit.check("register:" + _ip(request), 10, 3600)
    u = registration_service.register_student(db, body.model_dump())
    return {"success": True, "message": "Account created. You can now sign in.", "username": u.username}


@router.get("/admin/roster")
def roster(q: Optional[str] = Query(None, max_length=100), page: int = 1, page_size: int = 50,
           user: User = Depends(require("roster.manage")), db: Session = Depends(get_db)):
    page, page_size = max(page, 1), min(max(page_size, 1), 200)
    return registration_service.list_roster(db, q, page, page_size)


@router.post("/admin/roster")
def roster_add(body: RosterIn, user: User = Depends(require("roster.manage")), db: Session = Depends(get_db)):
    r = registration_service.add_roster(db, user, body.model_dump())
    return {"roster_id": r.roster_id, "student_number": r.student_number}


@router.post("/admin/roster/import")
def roster_import(body: RosterImportIn, user: User = Depends(require("roster.manage")), db: Session = Depends(get_db)):
    return registration_service.import_csv(db, user, body.csv)
