# Traceability - Chapter 3 manuscript to implementation
| Req | Implementation | Test |
|---|---|---|
| FR1 login, logout, attempt records, lockout | auth_service, `/auth/*`, LoginWindow | test_api (login, lockout), test_domain |
| FR2 account management | admin_service, `/users*`, UsersPage + UserDialog (Head Librarian tick) | test_api admin, test_verification |
| FR3 five roles, check before every action, denials recorded | domain/rbac, core/deps `require()`, `PERMISSION_DENIED` audit | test_domain Rbac, test_api, test_verification |
| FR4 one final PDF + metadata incl. course, adviser, dean | submission_service, `/submissions`, SubmissionForm | test_api TC-01/02, upload tests |
| FR5 Head Librarian final evaluation and archival approval | verification_service, `/verifications/*`, VerificationDialog | test_api workflow, test_domain |
| FR6 signatory checklist; return with remarks | domain/workflow `verify`, `signatory_verifications` | test_domain, test_api |
| FR7 store, checksum, reference no., Archived, indexing | verification_service + files_service + index_service | test_api archive tests |
| FR8 status, remarks, notifications | `/submissions/{id}` (verification_history), notifications | test_api, test_verification |
| FR9 metadata maintenance, recorded, re-indexed | repository_service.update_metadata | test_api metadata |
| FR10 publication status | repository_service.set_publication_status, `archived_visibility()` | test_verification |
| FR11 semantic search on title, abstract, keywords | search_service, index_service, all-MiniLM-L6-v2 | test_api TC-06/07, test_real_model |
| FR12 filters year, course, department, adviser, dean | repository_service.apply_filters, FilterBar | test_api filters |
| FR13 recommendations | search_service.recommendations | test_api |
| FR14 embedded viewer, no download | reader_service, ReaderDialog | test_api TC-08 |
| FR15 role-controlled companion files | `/repository/{id}/companions/{file}`, ResearchDetailDialog | test_verification |
| FR16 activity records and reports (admin) | audit/activity logs, reports_service, ReportsPage, LogsPage | test_api reports, TC-11 |
| FR17 departments, courses, settings, backup and restore | admin_service, backup_service, BackupPage, scripts/backup_now + restore_backup | test_verification backup |
| FR18 integration | `/api/v1/*` (documented in INTEGRATION.md); no official school API exists, so it stays an integration-ready interface | test_integration |
| NFR1 security | bcrypt, session + role check on every route, SQLAlchemy parameters, files only through the reader | test_api |
| NFR2 integrity | SHA-256 checked before archiving, FK constraints, duplicate detection | test_api archive-blocked, TC-02 |
| NFR3 no download | reader renders images only; manuscript never served as a file | TC-08, test_verification |
| NFR6 reliability and recovery | transactional audit; backup sets + safety backup on restore; Task Scheduler guide | test_verification backup |
| NFR7-NFR9 | local server + LAN client, no internet needed, Windows scripts | docs/README |
| NFR8 tests | pytest suites listed in TESTING.md | - |
