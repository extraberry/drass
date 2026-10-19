# Implementation decisions (PRD "TBD" items)
| Item | Decision |
|---|---|
| Panel quorum | ALL_ASSIGNED panelists must approve; any return/reject acts immediately. Panel is auto-assigned (active panelists of the work's department, else all) when the stage begins; ADVISER/ADMIN may override with *Assign Panel*. |
| Dean / Head Librarian assignment | One active dean (same department, else any) and one head librarian are assigned when their stage begins. |
| Password / lockout / idle | Min 8 chars; 5 failures → 15-minute lock; 20-minute idle timeout; 12-hour absolute session. All editable by ADMIN (`system_settings`). |
| Auth error | Generic "Invalid username or password." Locked/deactivated messages are shown only for existing accounts. |
| Duplicate rule | Same normalized title + same author set + same year (excluding DRAFT and REJECTED records) blocks submission. No admin override in v1. |
| Upload limits | Manuscript PDF 100 MB; companions 500 MB; configurable. Extension and magic bytes both checked; PDFs must open in PyMuPDF. Uploads are streamed (raw body) so large files are not held in memory. |
| Companion files | Stored and listed (metadata only). No download endpoint is exposed in v1. |
| Semantic threshold | 0.35 starting point, tunable by ADMIN; shown as "Semantic relevance: N%". |
| Recommendations | Cosine primary; small bounded metadata boost (program, department, category, keywords, year). On demand; not cached. Count configurable (default 5). |
| Archive failure policy | Files verified (exists + SHA-256) *before* the state change; failure leaves status unchanged, is audited and notifies admins. |
| Indexing failure | Work stays ARCHIVED; embedding FAILED with error; admins/head librarian notified; retried every 10 min and via *Reindex Failed*. |
| Visibility | Only ARCHIVED is visible to everyone; students see own works; reviewers see assigned non-draft works; external users ARCHIVED only. |
| Reader | Server renders one PNG per request (Cache-Control: no-store). No download/print/save. Deterrent only. |
| Optimistic lock | `research_works.version` + `expected_version` on review calls; one decision per assignment. |
| Schema creation | `create_all` for first install; Alembic configured, initial revision generated from models on a live MySQL (`--autogenerate`). |
| Search logging | Query text logged to activity_logs (truncated to 200 chars); switch off with setting `log_search_queries=false`. |
| Roles | The eight roles are fixed; no role deletion is exposed. |
| Guest access | The app opens in guest mode: Repository browse, filters, semantic search, record detail and related research work without login via `/public/*` endpoints (ARCHIVED records only, rate-limited per IP). **Guests cannot read manuscripts** — the reader needs a signed-in account (manuscripts may contain personal data). Non-public records return 404 to guests so their existence is not revealed. |
| Student self-registration | Only students on the registrar **roster** (`student_roster`, imported by ADMIN as CSV) can register. Required: student ID on the roster + matching last name; the account name comes from the roster, the role is always STUDENT. One account per student ID (`users.student_number` is unique). Failures use one generic message. Limitation: student IDs are not secret, so ID + surname is a weak check; stronger options (admin approval, school-email verification) are not implemented. |
