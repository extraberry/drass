from typing import Optional
from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=200)


class AuthorIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    student_number: Optional[str] = Field(None, max_length=30)


class SubmissionIn(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    abstract: Optional[str] = Field(None, max_length=20000)
    year: Optional[int] = Field(None, ge=1990, le=2100)
    program_id: Optional[int] = None
    department_id: Optional[int] = None
    category_id: Optional[int] = None
    adviser_id: Optional[int] = None
    authors: Optional[list[AuthorIn]] = Field(None, max_length=10)
    keywords: Optional[list[str]] = Field(None, max_length=15)


class ResubmitIn(BaseModel):
    change_notes: str = Field(min_length=1, max_length=5000)


class ReviewActionIn(BaseModel):
    comments: str = Field("", max_length=5000)
    expected_version: Optional[int] = None
    panel_offline: bool = False                                   # adviser approve only: panel already approved outside the system
    panel_offline_reference: str = Field("", max_length=300)      # e.g. letter date / reference no. (required when panel_offline)


class PanelIn(BaseModel):
    panelist_ids: list[int] = Field(min_length=1, max_length=10)


class SearchFilters(BaseModel):
    program_id: Optional[int] = None
    department_id: Optional[int] = None
    year: Optional[int] = None
    adviser_id: Optional[int] = None
    category_id: Optional[int] = None
    author: Optional[str] = Field(None, max_length=200)
    keyword: Optional[str] = Field(None, max_length=80)


class SemanticSearchIn(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    filters: SearchFilters = SearchFilters()
    limit: int = Field(20, ge=1, le=50)


class UserCreateIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(max_length=200)
    role: str
    full_name: str = Field(min_length=1, max_length=150)
    email: str = Field(max_length=150, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    student_number: Optional[str] = Field(None, max_length=30)
    department_id: Optional[int] = None


class UserPatchIn(BaseModel):
    role: Optional[str] = None
    full_name: Optional[str] = Field(None, max_length=150)
    email: Optional[str] = Field(None, max_length=150, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    student_number: Optional[str] = Field(None, max_length=30)
    department_id: Optional[int] = None


class ProfilePatchIn(BaseModel):
    full_name: Optional[str] = Field(None, max_length=150)
    email: Optional[str] = Field(None, max_length=150, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class PasswordChangeIn(BaseModel):
    old_password: str = Field(max_length=200)
    new_password: str = Field(max_length=200)


class PasswordResetIn(BaseModel):
    new_password: str = Field(max_length=200)


class SettingsIn(BaseModel):
    values: dict[str, str]


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    department_id: Optional[int] = None
    status: Optional[str] = Field(None, pattern="^(ACTIVE|INACTIVE)$")


class RebuildIn(BaseModel):
    mode: str = Field(pattern="^(failed|all)$")


class MetadataPatchIn(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    abstract: Optional[str] = Field(None, min_length=1, max_length=20000)
    keywords: Optional[list[str]] = Field(None, max_length=15)
    category_id: Optional[int] = None


class StudentRegisterIn(BaseModel):
    student_number: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9-]+$")
    last_name: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    email: str = Field(max_length=150, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(max_length=200)


class RosterIn(BaseModel):
    student_number: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9-]+$")
    last_name: str = Field(min_length=1, max_length=100)
    first_name: str = Field(min_length=1, max_length=100)
    department_id: Optional[int] = None


class RosterImportIn(BaseModel):
    csv: str = Field(max_length=2_000_000)


class ApiKeyCreateIn(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    scopes: list[str] = Field(min_length=1, max_length=5)
    expires_days: Optional[int] = Field(None, ge=1, le=3650)


class RosterSyncIn(BaseModel):
    students: list[dict] = Field(max_length=5000)


class OverrideIn(BaseModel):
    mode: str = Field(pattern="^(next|archive)$")
    reason: str = Field(min_length=5, max_length=2000)
    expected_version: Optional[int] = None
