# DRASS - Change log (latest round first)

## Round 15 - fonts match design A
- Body text now uses **Inter**, included in `client/app/resources/fonts/` (SIL Open Font License). Headings use **Source Serif 4** when its files are added to that folder (see `fonts/README.txt`); until then they fall back to Georgia. All `.ttf`/`.otf` files in that folder are loaded at start-up (`style.load_fonts`).

## Round 14 - graphite (C) becomes the default look, new app icon
- The app now opens in the dark Graphite theme by default (the first time after this update); the Light/Dark button still switches and the choice is remembered.
- New app icon: the open-book mark (navy book on a gold tile) (`client/app/resources/app_icon.png`, plus `app_icon.ico` for shortcuts). The Windows taskbar shows it instead of the Python icon.
- The logo in the header and on the login screen is the same in both themes: navy book on a gold tile (`logo_book.svg`).

## Round 13 - formal UI (design A "Institutional Navy" light, design C "Graphite" dark)
- `client/app/style.py`: new light and dark colour sets; Georgia headings with Segoe UI body text (both ship with Windows); flat navy header with a gold line (no rounded corners); white sidebar with a left accent bar on the selected item; cards and tables have a thin border; the tick colour follows the theme.
- New `client/app/resources/logo_book.svg` (open-book mark on a gold tile) used in the header and on the login screen. The school seal stays at the right of the header. The old overlapping ribbon is removed.
- The dark theme uses a teal accent; ticks and primary buttons use dark text on teal for contrast.
- Written, not run here (PySide6 is not available in the build sandbox). Check both themes on a PC and report anything that looks different from the mockups.

## Round 12 - student ID is the username
- Student self-registration no longer asks for a username. The account username is the student ID (stored in upper case), e.g. `2023-0101`.
- Sign-in accepts the student ID for any student account (case-insensitive), including accounts created earlier with another username, so no migration is needed.
- Login screen label: "Student ID / Username". Staff, faculty, administrator and external accounts still use their usernames.
- The Administrator can still edit a username; the student ID remains in the `student_number` column either way.
- Tests updated (`test_guest_register.py`); written, not run here.

## Round 11 - demo polish
- Product name is **DRASS** again everywhere (the interim "ResearchVault" name is removed from the client, server, scripts and docs). New reference numbers use `DRASS-<year>-<number>`; older `RV-` references are left as they are. If your `.env` has `APP_NAME=ResearchVault`, change or delete that line.
- Submission form: examples for Author(s) (`Full Name, Student Number`, one per line) and Keywords (comma-separated), as grey placeholders and as always-visible hints under the fields.
- PDF reader and paging buttons use plain text: `<< First`, `< Prev`, `Next >`, `Last >>` (also `< Previous` / `Next >`, `< Newer` / `Older >`).
- Tick boxes (and radio buttons) are now clearly visible in both light and dark mode, with a white tick on a filled box.
- Search speed: the embedding model is loaded when the server starts (it was loaded on the first search, which looked like a freeze) and repeated queries are cached; the client allows up to 2 minutes for the first search.
- New `scripts\reset_demo.bat` / `reset_demo.py` and `docs/DEMO_RESET.md` to reset the system before each demonstration.


Roles now: STUDENT, FACULTY, LIBRARY_STAFF (the Head Librarian is a designated Library Staff account), ADMIN, EXTERNAL_USER (guests). Backups go to a separate storage folder (`BACKUP_DIR`).
The system itself runs offline on the campus server. See `docs/BACKUP_AND_SYNC.md`.

## Round 10 - Aligned with the Chapter 3 manuscript (IT3BG1_MANUSCRIPT_Ch3_Revised)
Audit and gap list: `docs/MANUSCRIPT_ALIGNMENT.md`. Everything below is **written, not run** except the standard-library tests (`test_domain` 43, `test_migration` 9).
| Change | Status |
|---|---|
| Roles: ADVISER/HEAD_LIBRARIAN replaced by FACULTY + LIBRARY_STAFF; Head Librarian = `users.is_head_librarian` | Done, not run |
| Workflow: DRAFT -> PENDING_VERIFICATION -> RETURNED / ARCHIVED; adviser review, offline reference, Reject and admin override removed | Done (rules tested), API not run |
| Head Librarian signatory checklist (`signatory_verifications`), remarks, checksum check before archiving, approver and date recorded | Done, not run |
| Publication status Public / Restricted / Unpublished applied to repository, search, recommendations, reader, catalog | Done (rules tested), SQL not run |
| Dean on the submission and as a filter; "Program" shown as "Course"; category optional | Done, not run |
| Companion files: role-controlled download for Library Staff and the owning student | Done, not run |
| Administrator can no longer search or read research; reports are administrator-only; new report kinds | Done, not run |
| Backup & Recovery: backup service, admin page, `backup_now`/`restore_backup` scripts, Task Scheduler guide | Done, not run |
| Database migration `align_database_to_manuscript.py` (idempotent), `update_database.bat` rewritten | Done; migration logic tested on SQLite |
| Client: role navigation, Verification Queue/History, verification dialog, publication dialog, Head Librarian tick, Backup page, dean filter | Done, not run |
| Tests rewritten for the new workflow (`test_api`, `test_verification`, `test_migration`, helpers) | Done; API tests not run |
| Removed: `scripts/remove_panel_librarian_roles.py`, `scripts/backup_database.py`, `review_dialog.py`, `test_override_offline.py` | Done |

## Round 9 - Dashboard card spacing (matches the UI design canvas)
| Change | Status |
|---|---|
| Stat-card grid: row gap 14 -> 20 px and 26 px of space below the grid, so the card drop shadows are no longer clipped or covered | Done, not run |
| Admin dashboard: panel below the grid (190 px tall, max 980 px wide, 26 px under the grid, same panel colour in light #C9D1E0 and dark #17233B) | Done, not run |
| Card shadows follow the theme: soft navy in light mode, deeper black in dark mode (`card_shadow_rgba()` in `style.py`) | Done, not run |
| Canvas dashboards now show the same 10 admin cards as the app (panel/dean cards removed, "Pending final approval") | Done (design only) |

## Round 8 - Database update for the role changes
| Change | Status |
|---|---|
| `scripts\update_database.bat`: backup -> missing tables -> role/workflow clean-up -> search re-index, in one double-click | Written, not run on your database |
| Update script now fixes the Head Librarian role description, prints the roles left in the database and warns if no active Head Librarian exists | Done |
| `docs/DATABASE.md` lists the five roles and the valid statuses/stages | Done |

## Round 7 - Head Librarian gives the final approval
| Change | Status |
|---|---|
| New flow: Student -> Adviser (records the reference of the offline approval) -> **Head Librarian final approval** -> Archived. Status `UNDER_HEAD_LIBRARIAN_REVIEW` and stage `HEAD_LIBRARIAN` are back | Done, domain tests (45) pass |
| Head Librarian has a Review Queue and Review History; can Approve (no reference needed), Return or Reject; one active Head Librarian's approval is enough | Done |
| Adviser approval is refused if no active Head Librarian exists (nothing changes) | Done, API test written |
| Archiving (file check, search indexing, student notification) now happens at the final approval | Done |
| Admin: archive now, or "next" = move to the next approval stage; works from Submitted, Under Adviser Review, Under Head Librarian Review, Returned | Done |
| Dashboard: "Pending final approval" box for admin; Head Librarian sees pending reviews | Done |
| Upgrade script: works already waiting for the Head Librarian stay there and get a pending review for each active Head Librarian | Done, not run |
| API tests updated for the two-step approval | Written, not run |

## Round 6 - Head Librarian role kept (no approval duty; replaced by Round 7)
| Change | Status |
|---|---|
| HEAD_LIBRARIAN role restored as a **non-approving** role (browse, search, read, edit metadata of archived studies, Indexing Monitor, library reports) with its own menu and demo account `headlibrarian` | Done |
| It cannot review, approve, override or manage users (rule tested) | Done, domain tests |
| `remove_panel_librarian_roles.py`: no longer deletes HEAD_LIBRARIAN accounts; old LIBRARY_STAFF accounts are converted to HEAD_LIBRARIAN | Done, not run |

## Round 5 - Librarian and panel roles fully removed
| Change | Status |
|---|---|
| Library Staff (librarian) role removed: no role, no menu, no demo account `librarian`; metadata editing, indexing monitor and library reports are ADMIN only | Done |
| Legacy Panel / Dean / Head Librarian stages and statuses deleted from the code (they were only kept for old records) | Done |
| Wording cleaned: review tag is now `[OFFLINE APPROVAL – ref: …]`; dialogs, messages, docs and demo text no longer mention panel or librarian | Done |
| `scripts\remove_panel_librarian_roles.py` extended: also deletes/deactivates librarian accounts; works whose adviser is missing become SUBMITTED so the admin can archive them | Done, not run |
| Tests updated (41 domain tests pass; API tests not run) | Done |

## Round 4 - Offline only, admin controls, backup guide
| Change | Where | Status |
|---|---|---|
| Removed the live cloud database feature (copy to cloud MySQL, automatic fail-over, failback, cloud status page, Dockerfile, `docs/CLOUD.md`) | `server/app/db.py`, `main.py`, `core/config.py`, `routes_more.py`, `services/cloud_sync.py` (deleted), `scripts/cloud_sync.py` (deleted), Settings page, `.env.example` | Done |
| Cloud is now only a backup folder: step-by-step guide + one-click `scripts\backup_now.bat` (database `.sql` + `storage` copy) | `docs/BACKUP_AND_SYNC.md`, `scripts/backup_now.bat` | Done, not run on Windows |
| Admin can archive any submitted study that is not archived or rejected (submitted, under review, returned) with a reason; button "Archive this study…" | `domain/workflow.py` (`OVERRIDABLE`), `research_detail.py` | Done, domain rule tested |
| Account deletion was added, then **removed** at your request; admin keeps activate / deactivate | - | Net: no change to accounts |
| Tests: cloud tests removed (`test_upload_search.py` replaces `test_upload_search_cloud.py`); tests added for archiving submitted/returned studies | `server/tests/` | 42 domain tests pass; API tests not run |

## Round 3 - Limits, roles, guest reading, search
| Change | Status |
|---|---|
| Clear file-size limits written next to each upload (document, video, source code), stored in settings, published at `/public/upload-limits`; client refuses oversized files | Done |
| Panelist and Head Librarian roles removed; approval is offline: the adviser enters the reference of the offline approval to archive | Done |
| `scripts/remove_panel_librarian_roles.py` for existing databases | Done, not run |
| Guests read archived studies without an account (secure reader, rate limited, setting `guest_reading_enabled`) | Done |
| Semantic search rewritten: meaning + word matching (stems, typos, acronyms, phrases), multi-piece embeddings, default threshold 0.25, min query 2 chars | Done; real model not tested |
| Backup script and docs; README/DECISIONS/WORKFLOWS/API/TESTING updated | Done |

## Earlier rounds (from the project notes)
Password change, admin can edit usernames, database structure document, UI canvas, dashboard redesign, login title, Dean role removed, ResearchVault rename, integration API (API keys, roster sync). Details: `docs/IMPLEMENTATION_STATUS.md`.

## Still to do after updating an existing installation
1. `scripts\backup_database.py` (or `backup_now.bat`) before updating.
2. `scripts\remove_panel_librarian_roles.py` (type YES), once.
3. `scripts\rebuild_embeddings.py all`.
4. Remove any `CLOUD_*`, `DB_MODE`, `FILES_MIRROR_DIR` lines from `.env` (they are ignored now).
