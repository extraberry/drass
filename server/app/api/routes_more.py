"""Repository, search, recommendations, reader, reports, logs, admin."""
import threading
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..core.deps import current_user, require, role_of
from ..db import SessionLocal, get_db
from ..domain import rbac
from ..domain.errors import Forbidden, NotFound, ValidationFailed
from ..models import ActivityLog, AuditLog, FileRecord, ResearchWork, User, Embedding
from ..schemas.schemas import (BackupRestoreIn, MetadataPatchIn, NameIn, PasswordResetIn, PublicationIn, RebuildIn,
                               SemanticSearchIn, SettingsIn, UserCreateIn, UserPatchIn)
from ..services import (admin_service, backup_service, files_service, index_service, reader_service, reports_service,
                        repository_service, search_service)
from ..services.common import activity, audit, get_all_settings, set_setting
from ..services.serializers import user_dict, work_dict

router = APIRouter()


def _filters(program_id, department_id, year, adviser_id, dean_id, category_id, author, keyword) -> dict:
    return {"program_id": program_id, "department_id": department_id, "year": year, "adviser_id": adviser_id,
            "dean_id": dean_id, "category_id": category_id, "author": author, "keyword": keyword}


# ---------- repository ----------
@router.get("/repository")
def repository(program_id: Optional[int] = None, department_id: Optional[int] = None, year: Optional[int] = None,
               adviser_id: Optional[int] = None, dean_id: Optional[int] = None, category_id: Optional[int] = None,
               author: Optional[str] = Query(None, max_length=200), keyword: Optional[str] = Query(None, max_length=80),
               sort: str = "archived_at", order: str = "desc", page: int = 1, page_size: int = 20,
               publication_status: Optional[str] = None, user: User = Depends(require("repository.browse")),
               db: Session = Depends(get_db)):
    if publication_status and role_of(user).value != "LIBRARY_STAFF":
        publication_status = None                       # only Library Staff filter by publication status
    return repository_service.list_repository(
        db, user, _filters(program_id, department_id, year, adviser_id, dean_id, category_id, author, keyword),
        sort, order, page, page_size, publication_status)


@router.get("/repository/{work_id}")
def repository_detail(work_id: int, user: User = Depends(require("repository.browse")), db: Session = Depends(get_db)):
    w = repository_service.get_work_for_user(db, user, work_id)
    activity(db, user.user_id, "RESEARCH_VIEWED", "work", work_id)
    db.commit()
    d = repository_service.detail_for_user(db, user, w)
    d["can_read"] = True
    return d


@router.patch("/repository/{work_id}")
def repository_patch(work_id: int, body: MetadataPatchIn, user: User = Depends(require("metadata.maintain")),
                     db: Session = Depends(get_db)):
    w = repository_service.update_metadata(db, user, work_id, body.model_dump(exclude_unset=True))
    return work_dict(db, w)


@router.put("/repository/{work_id}/publication")
def repository_publication(work_id: int, body: PublicationIn, user: User = Depends(require("publication.manage")),
                           db: Session = Depends(get_db)):
    w = repository_service.set_publication_status(db, user, work_id, body.publication_status)
    return work_dict(db, w)


@router.get("/repository/{work_id}/companions/{file_id}")
def companion_file(work_id: int, file_id: int, user: User = Depends(require("companions.access")), db: Session = Depends(get_db)):
    """FR15: companion files (source code, video demonstrations) are for Library Staff and the owning student only.
    The manuscript PDF is never served as a file (FR14, NFR3)."""
    w = repository_service.get_work_for_user(db, user, work_id)
    if not rbac.can_access_companions(role_of(user), user.user_id, w.submitted_by):
        audit(db, user.user_id, "PERMISSION_DENIED", "file", file_id, "DENIED", "companion file")
        db.commit()
        raise Forbidden("You do not have permission to open companion files of this research.")
    f = db.get(FileRecord, file_id)
    if f is None or f.work_id != work_id or not f.is_active or f.file_type == "MANUSCRIPT":
        raise NotFound("File not found.")
    path = files_service.companion_path(f)
    audit(db, user.user_id, "COMPANION_FILE_OPENED", "file", file_id, details=f.original_filename[:200])
    db.commit()
    return FileResponse(path, media_type=f.mime_type or "application/octet-stream", filename=f.original_filename,
                        headers={"Cache-Control": "no-store"})


# ---------- search / recommendations ----------
@router.post("/search/semantic")
def semantic(body: SemanticSearchIn, user: User = Depends(require("search.semantic")), db: Session = Depends(get_db)):
    return search_service.semantic_search(db, user, body.query, body.filters.model_dump(), body.limit)


@router.get("/recommendations/{work_id}")
def recs(work_id: int, user: User = Depends(require("search.semantic")), db: Session = Depends(get_db)):
    return search_service.recommendations(db, user, work_id)


# ---------- reader ----------
@router.get("/reader/{work_id}/info")
def reader_info(work_id: int, user: User = Depends(require("reader.read")), db: Session = Depends(get_db)):
    return reader_service.info(db, user, work_id)


@router.get("/reader/{work_id}/pages/{page_number}")
def reader_page(work_id: int, page_number: int, scale: float = 1.5, user: User = Depends(require("reader.read")),
                db: Session = Depends(get_db)):
    png, meta = reader_service.render_page(db, user, work_id, page_number, scale)
    headers = {"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff",
               "Content-Disposition": "inline", "X-Page-Count": str(meta["page_count"]),
               "X-Page-Width": f"{meta['page_width']:.2f}", "X-Page-Height": f"{meta['page_height']:.2f}"}
    return Response(content=png, media_type="image/png", headers=headers)


# ---------- reports ----------
@router.get("/reports/{kind}")
def report(kind: str, date_from: Optional[str] = None, date_to: Optional[str] = None, program_id: Optional[int] = None,
           department_id: Optional[int] = None, status: Optional[str] = None,
           role: Optional[str] = None, user_id: Optional[int] = None, format: str = "json",
           user: User = Depends(require("reports.any")), db: Session = Depends(get_db)):
    f = {k: v for k, v in dict(date_from=date_from, date_to=date_to, program_id=program_id, department_id=department_id,
                               status=status, role=role, user_id=user_id).items() if v not in (None, "")}
    result = reports_service.run(db, user, kind, f)
    if format == "csv":
        return Response(reports_service.to_csv(result), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'})
    return result


# ---------- logs (read-only) ----------
@router.get("/audit-logs")
def audit_logs(user_id: Optional[int] = None, action: Optional[str] = Query(None, max_length=50),
               page: int = 1, page_size: int = 50, user: User = Depends(require("audit.read")), db: Session = Depends(get_db)):
    if page < 1 or not 1 <= page_size <= 200:
        raise ValidationFailed("Invalid pagination parameters.")
    stmt = select(AuditLog)
    if user_id: stmt = stmt.where(AuditLog.user_id == user_id)
    if action: stmt = stmt.where(AuditLog.action == action)
    rows = db.scalars(stmt.order_by(AuditLog.log_id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    names = {u.user_id: u.username for u in db.scalars(select(User)).all()}
    return {"items": [{"log_id": r.log_id, "timestamp": r.timestamp.isoformat(), "user": names.get(r.user_id, ""),
                       "action": r.action, "target": f"{r.target_type or ''} {r.target_id or ''}".strip(),
                       "result": r.result, "details": r.details} for r in rows], "page": page}


@router.get("/activity-logs")
def activity_logs(user_id: Optional[int] = None, event_type: Optional[str] = Query(None, max_length=50),
                  page: int = 1, page_size: int = 50, user: User = Depends(require("activity.read")), db: Session = Depends(get_db)):
    if page < 1 or not 1 <= page_size <= 200:
        raise ValidationFailed("Invalid pagination parameters.")
    stmt = select(ActivityLog)
    if user_id: stmt = stmt.where(ActivityLog.user_id == user_id)
    if event_type: stmt = stmt.where(ActivityLog.event_type == event_type)
    rows = db.scalars(stmt.order_by(ActivityLog.log_id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    names = {u.user_id: u.username for u in db.scalars(select(User)).all()}
    return {"items": [{"log_id": r.log_id, "timestamp": r.timestamp.isoformat(), "user": names.get(r.user_id, ""),
                       "event_type": r.event_type, "target": f"{r.target_type or ''} {r.target_id or ''}".strip(),
                       "details": r.details} for r in rows], "page": page}


# ---------- admin: users ----------
@router.get("/users")
def users(q: Optional[str] = Query(None, max_length=100), role: Optional[str] = None, status: Optional[str] = None,
          page: int = 1, page_size: int = 50, user: User = Depends(require("users.manage")), db: Session = Depends(get_db)):
    if page < 1 or not 1 <= page_size <= 200:
        raise ValidationFailed("Invalid pagination parameters.")
    r = admin_service.list_users(db, q, role, status, page, page_size)
    r["items"] = [user_dict(u) for u in r["items"]]
    return r


@router.post("/users")
def create_user(body: UserCreateIn, user: User = Depends(require("users.manage")), db: Session = Depends(get_db)):
    return user_dict(admin_service.create_user(db, user, body.model_dump()))


@router.patch("/users/{user_id}")
def patch_user(user_id: int, body: UserPatchIn, user: User = Depends(require("users.manage")), db: Session = Depends(get_db)):
    return user_dict(admin_service.patch_user(db, user, user_id, body.model_dump(exclude_unset=True)))


@router.post("/users/{user_id}/activate")
def activate(user_id: int, user: User = Depends(require("users.manage")), db: Session = Depends(get_db)):
    return user_dict(admin_service.set_active(db, user, user_id, True))


@router.post("/users/{user_id}/deactivate")
def deactivate(user_id: int, user: User = Depends(require("users.manage")), db: Session = Depends(get_db)):
    return user_dict(admin_service.set_active(db, user, user_id, False))


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, body: PasswordResetIn, user: User = Depends(require("users.manage")), db: Session = Depends(get_db)):
    admin_service.reset_password(db, user, user_id, body.new_password)
    return {"success": True}


# ---------- admin: settings & lookups ----------
@router.get("/admin/settings")
def get_settings_(user: User = Depends(require("settings.manage")), db: Session = Depends(get_db)):
    return get_all_settings(db)


@router.put("/admin/settings")
def put_settings(body: SettingsIn, user: User = Depends(require("settings.manage")), db: Session = Depends(get_db)):
    for k, v in body.values.items():
        set_setting(db, user, k, v)
    db.commit()
    return get_all_settings(db)


@router.get("/admin/lookups/{kind}")
def admin_lookups(kind: str, user: User = Depends(require("settings.manage")), db: Session = Depends(get_db)):
    if kind not in admin_service.LOOKUPS:
        raise NotFound("Unknown list.")
    return {"items": admin_service.lookup_rows(db, kind, include_inactive=True)}


@router.post("/admin/lookups/{kind}")
def add_lookup(kind: str, body: NameIn, user: User = Depends(require("settings.manage")), db: Session = Depends(get_db)):
    if kind not in admin_service.LOOKUPS:
        raise NotFound("Unknown list.")
    return admin_service.upsert_lookup(db, user, kind, body.model_dump())


@router.patch("/admin/lookups/{kind}/{item_id}")
def edit_lookup(kind: str, item_id: int, body: NameIn, user: User = Depends(require("settings.manage")), db: Session = Depends(get_db)):
    if kind not in admin_service.LOOKUPS:
        raise NotFound("Unknown list.")
    return admin_service.upsert_lookup(db, user, kind, body.model_dump(exclude_unset=True), item_id)


@router.get("/admin/roles")
def roles(user: User = Depends(require("users.manage")), db: Session = Depends(get_db)):
    from ..models import Role as R
    return {"items": [{"role_id": r.role_id, "role_name": r.role_name, "description": r.description,
                       "system_required": True} for r in db.scalars(select(R)).all()]}


# ---------- admin: indexing ----------
@router.get("/admin/indexing")
def indexing(user: User = Depends(require("indexing.view")), db: Session = Depends(get_db)):
    s = index_service.stats(db)
    s["threshold"] = float(get_all_settings(db)["semantic_threshold"])
    s["failures"] = index_service.failures(db)
    return s


@router.post("/admin/indexing/rebuild")
def rebuild(body: RebuildIn, tasks: BackgroundTasks, user: User = Depends(require("indexing.manage")),
            db: Session = Depends(get_db)):
    if index_service.PROGRESS["running"]:
        raise ValidationFailed("A rebuild is already running.")
    audit(db, user.user_id, "EMBEDDING_REBUILD_REQUESTED", "index", None, details=body.mode)
    db.commit()
    tasks.add_task(index_service.rebuild, SessionLocal, body.mode, user.user_id)
    return {"success": True, "started": body.mode}


# ---------- admin: backup and restoration (FR17, NFR6) ----------
@router.get("/admin/backups")
def backups(user: User = Depends(require("backup.manage"))):
    return {"items": backup_service.list_backups(), "backup_dir": str(backup_service.backup_root())}


@router.post("/admin/backups")
def backup_now(user: User = Depends(require("backup.manage")), db: Session = Depends(get_db)):
    info = backup_service.create_backup(label="manual")
    audit(db, user.user_id, "BACKUP_CREATED", "backup", info["name"], details=f"{info['file_count']} files")
    db.commit()
    return info


@router.post("/admin/backups/restore")
def backup_restore(body: BackupRestoreIn, user: User = Depends(require("backup.manage")), db: Session = Depends(get_db)):
    if body.confirm != "RESTORE":
        raise ValidationFailed("Type RESTORE to confirm the restoration.", {"confirm": "Type RESTORE."})
    uid, name = user.user_id, body.name
    db.close()                                                  # release this request's connection before the database is replaced
    result = backup_service.restore_backup(name)               # takes a safety backup first, then replaces database and files
    from ..db import SessionLocal
    with SessionLocal() as db2:                                # the restored database is the new truth: record the action there too
        audit(db2, uid, "BACKUP_RESTORED", "backup", name, details=f"safety backup {result['safety_backup']}")
        db2.commit()
    return result
