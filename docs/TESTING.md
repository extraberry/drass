# Testing
```
.venv\Scripts\python.exe -m pytest                 # everything (SQLite, hash embedder)
.venv\Scripts\python.exe -m pytest server/tests/test_api.py -k tc06 -vv
.venv\Scripts\python.exe -m unittest server.tests.test_domain
```
| File | Covers |
|---|---|
| `server/tests/test_domain.py` | manuscript workflow (checklist rules), RBAC and publication-status visibility, duplicates, file validation, lockout/session rules, cosine/threshold/recommendation logic |
| `server/tests/test_verification.py` | publication-status visibility (Public / Restricted / Unpublished), companion files, administrator boundaries, Head Librarian designation, backup and restore, username change, notifications |
| `server/tests/test_migration.py` | the old-to-manuscript database migration on a SQLite copy of the old schema (stdlib only) |
| `server/tests/test_upload_search.py` | published upload limits, per-kind size limits, words/acronyms/typos in search, old single-vector embeddings |
| `server/tests/test_guest_register.py` | guest browse/search/reading, student sign-up |
| `server/tests/test_api.py` | auth, RBAC & permission audit, TC-01…TC-12, submission/upload validation, Head Librarian verification (return / resubmit / archive + embedding), search/filters/pagination, reader (needs PyMuPDF), reports RBAC/CSV, admin, settings |
| `server/tests/test_real_model.py` | real MiniLM semantic check (skipped unless the model is installed) |
| `client/tests/test_api_client.py` | client error translation (no GUI) |
The API tests use a **test-only hash embedder** (`EMBEDDER=hash`) so they run offline; it is a bag-of-words toy, so TC-06 here verifies the pipeline (ranking, threshold, filters). True semantic quality is checked by `test_real_model.py`. Performance has not been measured yet; record results here after running on the target hardware.

**Run in the authoring sandbox:** only `test_domain` (43 tests) and `test_migration` (9 tests) - both standard library only. Everything else needs the installed dependencies and has not been run yet.
