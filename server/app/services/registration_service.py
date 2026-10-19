"""Student self-registration (verified against the roster) and roster maintenance."""
import csv
import io
import re
import unicodedata
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..core.security import hash_password
from ..domain import auth_rules as ar
from ..domain.errors import Conflict, ValidationFailed
from ..models import Department, Role as RoleModel, StudentRoster, User
from .common import audit, auth_policy

GENERIC = "We could not verify these details. Check your student ID and last name, or contact the library or registrar."
SN_RE = re.compile(r"^[A-Za-z0-9-]{3,30}$")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", s or "").lower())


def register_student(db: Session, d: dict) -> User:
    sn = d["student_number"].strip().upper()
    row = db.scalar(select(StudentRoster).where(StudentRoster.student_number == sn, StudentRoster.status == "ACTIVE"))
    if row is None or _norm(row.last_name) != _norm(d["last_name"]):
        audit(db, None, "STUDENT_REGISTER_FAILED", "registration", None, "FAILED", "verification failed")
        db.commit()
        raise ValidationFailed(GENERIC, {"student_number": "Could not be verified."})
    if db.scalar(select(User).where(User.student_number == sn)):
        raise Conflict("An account already exists for this student ID. Ask the administrator to reset your password if you forgot it.")
    if db.scalar(select(User).where(User.username == d["username"])):
        raise ValidationFailed("That username is taken.", {"username": "Already taken."})
    if db.scalar(select(User).where(User.email == d["email"])):
        raise ValidationFailed("That email is already registered.", {"email": "Already registered."})
    problems = ar.password_problems(d["password"], auth_policy(db))
    if problems:
        raise ValidationFailed(problems[0], {"password": problems[0]})
    role = db.scalar(select(RoleModel).where(RoleModel.role_name == "STUDENT"))
    u = User(username=d["username"], password_hash=hash_password(d["password"]), role_id=role.role_id,
             full_name=f"{row.first_name} {row.last_name}", email=d["email"], student_number=sn,
             department_id=row.department_id)
    db.add(u)
    try:
        db.flush()
        audit(db, u.user_id, "STUDENT_REGISTERED", "user", u.user_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict("An account already exists for this student ID or username.")
    return u


def list_roster(db: Session, q, page: int, page_size: int) -> dict:
    stmt = select(StudentRoster)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(StudentRoster.student_number.ilike(like), StudentRoster.last_name.ilike(like), StudentRoster.first_name.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(StudentRoster.student_number).offset((page - 1) * page_size).limit(page_size)).all()
    claimed = set(db.scalars(select(User.student_number).where(User.student_number.in_([r.student_number for r in rows]))).all()) if rows else set()
    return {"total": total, "items": [{"roster_id": r.roster_id, "student_number": r.student_number, "last_name": r.last_name,
                                       "first_name": r.first_name, "status": r.status,
                                       "account": "Registered" if r.student_number in claimed else "Not registered"} for r in rows]}


def add_roster(db: Session, actor: User, d: dict) -> StudentRoster:
    sn = d["student_number"].strip().upper()
    if db.scalar(select(StudentRoster).where(StudentRoster.student_number == sn)):
        raise Conflict("That student number is already on the roster.")
    r = StudentRoster(student_number=sn, last_name=d["last_name"].strip(), first_name=d["first_name"].strip(), department_id=d.get("department_id"))
    db.add(r)
    audit(db, actor.user_id, "ROSTER_ADDED", "roster", sn)
    db.commit()
    return r


def import_csv(db: Session, actor: User, text: str) -> dict:
    """Header row required: student_number,last_name,first_name[,department]. Existing numbers are skipped."""
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    need = {"student_number", "last_name", "first_name"}
    if not reader.fieldnames or not need <= {h.strip().lower() for h in reader.fieldnames}:
        raise ValidationFailed("CSV must have the columns: student_number, last_name, first_name (department optional).")
    depts = {d.department_name.lower(): d.department_id for d in db.scalars(select(Department)).all()}
    have = set(db.scalars(select(StudentRoster.student_number)).all())
    added, skipped, errors = 0, 0, []
    for i, raw in enumerate(reader, start=2):
        if i > 5002:
            errors.append("Stopped at 5000 rows."); break
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        sn = row.get("student_number", "").upper()
        if not SN_RE.match(sn) or not row.get("last_name") or not row.get("first_name"):
            errors.append(f"Row {i}: invalid or missing values"); continue
        if sn in have:
            skipped += 1; continue
        db.add(StudentRoster(student_number=sn, last_name=row["last_name"], first_name=row["first_name"],
                             department_id=depts.get(row.get("department", "").lower())))
        have.add(sn); added += 1
    audit(db, actor.user_id, "ROSTER_IMPORTED", "roster", None, details=f"added={added} skipped={skipped} errors={len(errors)}")
    db.commit()
    return {"added": added, "skipped": skipped, "errors": errors[:20]}
