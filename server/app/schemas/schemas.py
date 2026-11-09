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
    dean_id: Optional[int] = None
    authors: Optional[list[AuthorIn]] = Field(None, max_length=10)
    keywords: Optional[list[str]] = Field(None, max_length=15)


class ResubmitIn(BaseModel):
    change_notes: str = Field(min_length=1, max_length=5000)


class VerificationIn(BaseModel):
    """Head Librarian's signatory verification (FR5, FR6)."""
    decision: str = Field(pattern="^(APPROVE|RETURN)$")
    adviser_signed: bool = False
    panelists_signed: bool = False
    dean_signed: bool = False
    researchers_signed: bool = False
    sheet_complete: bool = False
    remarks: str = Field("", max_length=5000)
    publication_status: Optional[str] = Field(None, pattern="^(PUBLIC|RESTRICTED|UNPUBLISHED)$")
    expected_version: Optional[int] = None


class PublicationIn(BaseModel):
    publication_status: str = Field(pattern="^(PUBLIC|RESTRICTED|UNPUBLISHED)$")


class SearchFilters(BaseModel):
    program_id: Optional[int] = None
    department_id: Optional[int] = None
    year: Optional[int] = None
    adviser_id: Optional[int] = None
    dean_id: Optional[int] = None
    category_id: Optional[int] = None
    author: Optional[str] = Field(None, max_length=200)
    keyword: Optional[str] = Field(None, max_length=80)


class SemanticSearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
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
    is_head_librarian: bool = False


class UserPatchIn(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    role: Optional[str] = None
    full_name: Optional[str] = Field(None, max_length=150)
    email: Optional[str] = Field(None, max_length=150, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    student_number: Optional[str] = Field(None, max_length=30)
    department_id: Optional[int] = None
    is_head_librarian: Optional[bool] = None


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
    year: Optional[int] = Field(None, ge=1990, le=2100)
    program_id: Optional[int] = None
    department_id: Optional[int] = None
    adviser_id: Optional[int] = None
    dean_id: Optional[int] = None
    authors: Optional[list[AuthorIn]] = Field(None, max_length=10)


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


class BackupRestoreIn(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    confirm: str = Field(max_length=20)            # must be the word RESTORE
