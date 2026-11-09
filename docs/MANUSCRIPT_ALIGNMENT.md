# Manuscript alignment - audit and result
Source of truth: `IT3BG1_MANUSCRIPT_Ch3_Revised.docx` (Chapter 3). The manuscript was not changed.

## Audit: what differed, and what was done
| Area | Before | Manuscript | Now |
|---|---|---|---|
| Roles | Student, Adviser, Head Librarian, Admin, External | Student, Faculty, Library Staff, Administrator, External User | Done. Head Librarian is a flag on Library Staff |
| Submission | metadata + manuscript, optional companions; no dean | one final PDF with approval sheet; course, adviser, dean | Done (dean added, Course label, category optional) |
| Approval | Adviser review with offline reference, then Head Librarian; Reject; admin override | Head Librarian verifies signatories, returns with remarks or archives | Done. Adviser stage, reject and override removed |
| Statuses | 7 | Pending Verification, Returned, Archived (+ draft) | Done |
| Archive record | archived_at | + approving librarian, date, checksum verified, reference no. | Done (`archived_by`, checksum check) |
| Publication status | none | Public / Restricted / Unpublished, enforced | Done in every read path |
| Companion files | listed only | role-controlled access | Done (Library Staff + owner) |
| Admin | could browse/search/archive | no research access; reports, logs, backup/restore | Done |
| Reports | per-role | administrator | Done |
| Search | unchanged | title, abstract, keywords, all-MiniLM-L6-v2, filters incl. dean | Kept; dean filter added |
| Recommendations | unchanged | related by title, abstract, keywords | Kept; visibility applied |
| Backup / restore | script copying files | database + files, regular, documented restore | Done (service, page, scripts, guide) |
| FR18 | integration API | integrate if an official API exists, else future work | Kept as documented interface; none exists |

## Kept because it is consistent with the manuscript
Login/lockout/idle timeout, bcrypt, secure reader, duplicate check, semantic search and recommendations, guest access through `/public/*`, student roster registration, audit and activity logs, indexing monitor, API-key integration interface, light/dark themes.

## Not specified by the manuscript, deliberately not added
Reject, in-system adviser/panel/dean review, administrator override, email notifications, PDF export of reports.

## Known limits
- Nothing except the standard-library tests could be run where this was written: install the dependencies and run `pytest`, then the checklist in `docs/DEBUGGING.md`.
- Guests/External Users can read Public research only while the setting `guest_reading_enabled` is on (default on).
- Existing databases must run `scripts\update_database.bat` once.
