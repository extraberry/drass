"""Integration API (stable, versioned under /api/v1, authenticated by X-API-Key) + API-key administration.
Internal desktop-client routes are NOT versioned; only /api/v1/* is covered by the compatibility promise."""
from typing import Optional
from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy.orm import Session
from ..core.deps import require
from ..db import get_db
from ..models import ApiKey, User
from ..schemas.schemas import ApiKeyCreateIn, RosterSyncIn
from ..services import integration_service as svc
from ..services import registration_service

router = APIRouter()
V1 = "/api/v1"


def api_key(scope: str):
    def dep(request: Request, x_api_key: Optional[str] = Header(None), db: Session = Depends(get_db)) -> ApiKey:
        return svc.authenticate(db, x_api_key, scope, request.client.host if request.client else "unknown")
    return dep


@router.get(V1 + "/ping")
def ping():
    return {"service": "ResearchVault", "api_version": "v1", "status": "ok"}


@router.post(V1 + "/integration/roster")
def sync_roster(body: RosterSyncIn, key: ApiKey = Depends(api_key("roster:write")), db: Session = Depends(get_db)):
    return registration_service.sync_roster(db, body.students, source=key.name)


@router.get(V1 + "/catalog/works")
def catalog_list(archived_since: Optional[str] = Query(None, max_length=40), page: int = 1, page_size: int = 50,
                 format: str = Query("json", pattern="^(json|dc)$"), key: ApiKey = Depends(api_key("catalog:read")),
                 db: Session = Depends(get_db)):
    data = svc.list_catalog(db, archived_since, page, page_size)
    if format == "dc":
        return Response(svc.to_dublin_core(data["items"]), media_type="application/xml",
                        headers={"X-Total-Count": str(data["total"])})
    return data


@router.get(V1 + "/catalog/works/{work_id}")
def catalog_one(work_id: int, key: ApiKey = Depends(api_key("catalog:read")), db: Session = Depends(get_db)):
    return svc.get_catalog_record(db, work_id)


# ---- administration of keys (ADMIN only; internal route, not versioned) ----
@router.get("/admin/api-keys")
def list_keys(user: User = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    return {"items": svc.list_keys(db), "scopes": svc.SCOPES}


@router.post("/admin/api-keys")
def create_key(body: ApiKeyCreateIn, user: User = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    k, raw = svc.create_key(db, user, body.name, body.scopes, body.expires_days)
    return {**svc.key_dict(k), "api_key": raw, "notice": "Copy this key now. It cannot be shown again."}


@router.post("/admin/api-keys/{key_id}/revoke")
def revoke_key(key_id: int, user: User = Depends(require("integrations.manage")), db: Session = Depends(get_db)):
    svc.revoke_key(db, user, key_id)
    return {"success": True}
