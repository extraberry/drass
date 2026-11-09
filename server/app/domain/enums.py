"""Core enumerations for DRASS (names follow the capstone manuscript, Chapter 3)."""
from enum import Enum


class Role(str, Enum):
    """The five system roles of manuscript Table 5. The Head Librarian is a Library Staff account with is_head_librarian set."""
    STUDENT = "STUDENT"
    FACULTY = "FACULTY"                 # advisers, panelists and deans (they sign outside the system)
    LIBRARY_STAFF = "LIBRARY_STAFF"
    ADMIN = "ADMIN"                     # "Administrator"
    EXTERNAL_USER = "EXTERNAL_USER"


class Status(str, Enum):
    """Submission status (FR8: Pending Verification, Returned or Archived; DRAFT before the student submits)."""
    DRAFT = "DRAFT"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    RETURNED = "RETURNED"
    ARCHIVED = "ARCHIVED"


class PublicationStatus(str, Enum):
    """FR10: assigned by Library Staff to an archived work."""
    PUBLIC = "PUBLIC"
    RESTRICTED = "RESTRICTED"
    UNPUBLISHED = "UNPUBLISHED"


class Decision(str, Enum):
    """Result of the Head Librarian's signatory verification."""
    APPROVE = "APPROVE"                 # final archival approval
    RETURN = "RETURN"                   # returned to the student with remarks


class FileType(str, Enum):
    MANUSCRIPT = "MANUSCRIPT"           # the one final PDF: manuscript + completed approval sheet
    SOURCE_CODE = "SOURCE_CODE"
    VIDEO = "VIDEO"
    OTHER_COMPANION = "OTHER_COMPANION"
