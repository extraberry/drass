"""API keys for external systems + read-only catalog export (integration-ready design; no integrations are bundled)."""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
from xml.sax.saxutils import escape
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..core import ratelimit
from ..core.timeutil import utcnow
from ..domain.errors import AuthFailed, Forbidden, NotFound, ValidationFailed
from ..models import ApiKey, ResearchWork, User
from .common import audit
from .serializers import work_dict

SCOPES = {"roster:write": "Push/sync the student roster", "catalog:read": "Read metadata of archived research (no manuscripts)"}
PUBLISHER = "Mary the Queen College of Quezon City, Inc."


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_key(db: Session, actor: User, name: str, scopes: list, expires_days: Optional[int]) -> tuple[ApiKey, str]:
    scopes = sorted(set(scopes))
    if not scopes or any(s not in SCOPES for s in scopes):
        raise ValidationFailed(f"Scopes must be from: {', '.join(SCOPES)}.", {"scopes": "Invalid scope."})
    raw = "drass_" + secrets.token_urlsafe(32)
    k = ApiKey(name=name.strip(), key_prefix=raw[:12], key_hash=_hash(raw), scopes=",".join(scopes), created_by=actor.user_id,
               expires_at=utcnow() + timedelta(days=expires_days) if expires_days else None)
    db.add(k); db.flush()
    audit(db, actor.user_id, "API_KEY_CREATED", "api_key", k.key_id, details=f"{k.name} scopes={k.scopes}")
    db.commit()
    return k, raw                      # the raw key is returned once and never stored


def key_dict(k: ApiKey) -> dict:
    return {"key_id": k.key_id, "name": k.name, "key_prefix": k.key_prefix, "scopes": k.scopes, "status": k.status,
            "created_at": k.created_at.isoformat(), "expires_at": k.expires_at.isoformat() if k.expires_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None}


def list_keys(db: Session) -> list[dict]:
    return [key_dict(k) for k in db.scalars(select(ApiKey).order_by(ApiKey.key_id.desc())).all()]


def revoke_key(db: Session, actor: User, key_id: int) -> None:
    k = db.get(ApiKey, key_id)
    if k is None:
        raise NotFound("API key not found.")
    k.status = "REVOKED"
    audit(db, actor.user_id, "API_KEY_REVOKED", "api_key", key_id, details=k.name)
    db.commit()


def authenticate(db: Session, raw: Optional[str], scope: str, ip: str) -> ApiKey:
    k = db.scalar(select(ApiKey).where(ApiKey.key_hash == _hash(raw))) if raw and raw.startswith("drass_") else None
    now = utcnow()
    if k is None or k.status != "ACTIVE" or (k.expires_at and now >= k.expires_at):
        ratelimit.check("apikey-fail:" + ip, 30, 60)
        audit(db, None, "API_KEY_REJECTED", "api_key", k.key_id if k else None, "DENIED", f"ip={ip}")
        db.commit()
        raise AuthFailed("Invalid, expired or revoked API key.")
    if scope not in k.scopes.split(","):
        audit(db, None, "API_KEY_REJECTED", "api_key", k.key_id, "DENIED", f"missing scope {scope}")
        db.commit()
        raise Forbidden(f"This API key does not have the '{scope}' scope.")
    ratelimit.check("apikey:" + k.key_prefix, 300, 60)
    k.last_used_at = now
    db.commit()
    return k


# ---------- catalog (metadata only: never files, paths, student numbers or account data) ----------
def record(db: Session, w: ResearchWork) -> dict:
    d = work_dict(db, w)
    return {"id": d["work_id"], "reference_no": d["reference_no"], "title": d["title"], "abstract": d["abstract"], "year": d["year"],
            "authors": [a["name"] for a in d["authors"]], "program": d["program"], "department": d["department"],
            "category": d["category"], "adviser": d["adviser"], "keywords": d["keywords"], "archived_at": d["archived_at"]}


def list_catalog(db: Session, archived_since: Optional[str], page: int, page_size: int) -> dict:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValidationFailed("Invalid pagination parameters.")
    stmt = select(ResearchWork).where(ResearchWork.current_status == "ARCHIVED")
    if archived_since:
        try:
            stmt = stmt.where(ResearchWork.archived_at >= datetime.fromisoformat(archived_since))
        except ValueError:
            raise ValidationFailed("archived_since must be an ISO date, e.g. 2026-01-31 or 2026-01-31T08:00:00.")
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(ResearchWork.archived_at, ResearchWork.work_id).offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [record(db, w) for w in rows]}


def get_catalog_record(db: Session, work_id: int) -> dict:
    w = db.get(ResearchWork, work_id)
    if w is None or w.current_status != "ARCHIVED":
        raise NotFound("Record not found.")
    return record(db, w)


def to_dublin_core(items: list[dict]) -> str:
    """Simple Dublin Core (oai_dc elements) so library systems can harvest the catalog."""
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<records xmlns:dc="http://purl.org/dc/elements/1.1/">']
    for r in items:
        out.append("<record>")
        out.append(f"<dc:identifier>{escape(r['reference_no'] or str(r['id']))}</dc:identifier>")
        out.append(f"<dc:title>{escape(r['title'])}</dc:title>")
        out += [f"<dc:creator>{escape(a)}</dc:creator>" for a in r["authors"]]
        out += [f"<dc:subject>{escape(k)}</dc:subject>" for k in r["keywords"]]
        out.append(f"<dc:description>{escape(r['abstract'])}</dc:description>")
        out.append(f"<dc:publisher>{escape(PUBLISHER)}</dc:publisher>")
        if r["adviser"]: out.append(f"<dc:contributor>{escape(r['adviser'])}</dc:contributor>")
        if r["year"]: out.append(f"<dc:date>{r['year']}</dc:date>")
        out.append("<dc:type>Thesis or capstone project</dc:type><dc:language>en</dc:language>")
        out.append("</record>")
    out.append("</records>")
    return "\n".join(out)
