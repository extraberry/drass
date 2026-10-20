"""SQLAlchemy models (PRD s8). Works on MySQL 8 and SQLite (tests)."""
from datetime import datetime
from typing import Optional
from sqlalchemy import (Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .core.timeutil import utcnow
from .db import Base

PK = dict(primary_key=True, autoincrement=True)


class Role(Base):
    __tablename__ = "roles"
    role_id: Mapped[int] = mapped_column(Integer, **PK)
    role_name: Mapped[str] = mapped_column(String(30), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")


class Department(Base):
    __tablename__ = "departments"
    department_id: Mapped[int] = mapped_column(Integer, **PK)
    department_name: Mapped[str] = mapped_column(String(150), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class Program(Base):
    __tablename__ = "programs"
    program_id: Mapped[int] = mapped_column(Integer, **PK)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.department_id"), index=True)
    program_name: Mapped[str] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class ResearchCategory(Base):
    __tablename__ = "research_categories"
    category_id: Mapped[int] = mapped_column(Integer, **PK)
    category_name: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(Integer, **PK)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.role_id"), index=True)
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(150), unique=True)
    student_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True, unique=True)   # one student, one account
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.department_id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    role: Mapped["Role"] = relationship(lazy="joined")


class ResearchWork(Base):
    __tablename__ = "research_works"
    work_id: Mapped[int] = mapped_column(Integer, **PK)
    reference_no: Mapped[Optional[str]] = mapped_column(String(30), unique=True, nullable=True)
    title: Mapped[str] = mapped_column(String(500), default="", index=True)
    abstract: Mapped[str] = mapped_column(Text, default="")
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    program_id: Mapped[Optional[int]] = mapped_column(ForeignKey("programs.program_id"), nullable=True, index=True)
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.department_id"), nullable=True, index=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("research_categories.category_id"), nullable=True, index=True)
    adviser_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    current_status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)
    current_revision_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dup_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=0)       # optimistic lock
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ResearchAuthor(Base):
    __tablename__ = "research_authors"
    author_id: Mapped[int] = mapped_column(Integer, **PK)
    work_id: Mapped[int] = mapped_column(ForeignKey("research_works.work_id"), index=True)
    author_name: Mapped[str] = mapped_column(String(200), index=True)
    student_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    author_order: Mapped[int] = mapped_column(Integer, default=1)


class Keyword(Base):
    __tablename__ = "keywords"
    keyword_id: Mapped[int] = mapped_column(Integer, **PK)
    keyword_text: Mapped[str] = mapped_column(String(80), unique=True)


class ResearchKeyword(Base):
    __tablename__ = "research_keywords"
    work_id: Mapped[int] = mapped_column(ForeignKey("research_works.work_id"), primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.keyword_id"), primary_key=True)


class Revision(Base):
    __tablename__ = "revisions"
    __table_args__ = (UniqueConstraint("work_id", "revision_number"),)
    revision_id: Mapped[int] = mapped_column(Integer, **PK)
    work_id: Mapped[int] = mapped_column(ForeignKey("research_works.work_id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    change_notes: Mapped[str] = mapped_column(Text, default="")
    metadata_snapshot: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class FileRecord(Base):
    __tablename__ = "files"
    file_id: Mapped[int] = mapped_column(Integer, **PK)
    work_id: Mapped[int] = mapped_column(ForeignKey("research_works.work_id"), index=True)
    revision_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_type: Mapped[str] = mapped_column(String(20))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(100), unique=True)
    storage_path: Mapped[str] = mapped_column(String(500))      # relative to storage root; never sent to clients
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256_checksum: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ReviewAssignment(Base):
    __tablename__ = "review_assignments"
    assignment_id: Mapped[int] = mapped_column(Integer, **PK)
    work_id: Mapped[int] = mapped_column(ForeignKey("research_works.work_id"), index=True)
    stage: Mapped[str] = mapped_column(String(20), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")   # PENDING/DONE/CANCELLED
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Review(Base):
    __tablename__ = "reviews"
    review_id: Mapped[int] = mapped_column(Integer, **PK)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("review_assignments.assignment_id"), unique=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("research_works.work_id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    decision: Mapped[str] = mapped_column(String(10))
    comments: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class StatusHistory(Base):
    __tablename__ = "status_history"
    history_id: Mapped[int] = mapped_column(Integer, **PK)
    work_id: Mapped[int] = mapped_column(ForeignKey("research_works.work_id"), index=True)
    from_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str] = mapped_column(String(40))
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Embedding(Base):
    __tablename__ = "embeddings"
    embedding_id: Mapped[int] = mapped_column(Integer, **PK)
    work_id: Mapped[int] = mapped_column(ForeignKey("research_works.work_id"), unique=True)
    model_name: Mapped[str] = mapped_column(String(100), default="")
    dimension: Mapped[int] = mapped_column(Integer, default=0)
    dtype: Mapped[str] = mapped_column(String(20), default="float32")
    vector_blob: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    indexed_text_hash: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)  # PENDING/COMPLETE/FAILED/STALE
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"
    notification_id: Mapped[int] = mapped_column(Integer, **PK)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(30), default="INFO")
    target_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class SessionRecord(Base):
    __tablename__ = "sessions"
    session_id: Mapped[int] = mapped_column(Integer, **PK)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    session_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    log_id: Mapped[int] = mapped_column(Integer, **PK)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(50), index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    result: Mapped[str] = mapped_column(String(20), default="SUCCESS")
    details: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    log_id: Mapped[int] = mapped_column(Integer, **PK)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    details: Mapped[str] = mapped_column(Text, default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    setting_id: Mapped[int] = mapped_column(Integer, **PK)
    setting_key: Mapped[str] = mapped_column(String(60), unique=True)
    setting_value: Mapped[str] = mapped_column(String(255))
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class StudentRoster(Base):
    """Registrar-supplied list of enrolled students; only these may self-register."""
    __tablename__ = "student_roster"
    roster_id: Mapped[int] = mapped_column(Integer, **PK)
    student_number: Mapped[str] = mapped_column(String(30), unique=True)
    last_name: Mapped[str] = mapped_column(String(100))
    first_name: Mapped[str] = mapped_column(String(100))
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.department_id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ApiKey(Base):
    """Credential for an external system (never a person). Only the SHA-256 hash is stored."""
    __tablename__ = "api_keys"
    key_id: Mapped[int] = mapped_column(Integer, **PK)
    name: Mapped[str] = mapped_column(String(100))
    key_prefix: Mapped[str] = mapped_column(String(16), index=True)      # shown in lists to identify the key
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[str] = mapped_column(String(200))                       # comma separated: roster:write,catalog:read
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")      # ACTIVE / REVOKED
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
