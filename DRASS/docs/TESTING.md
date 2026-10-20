# Testing
```
.venv\Scripts\python.exe -m pytest                 # everything (SQLite, hash embedder)
.venv\Scripts\python.exe -m pytest server/tests/test_api.py -k tc06 -vv
.venv\Scripts\python.exe -m unittest server.tests.test_domain
```
| File | Covers |
|---|---|
| `server/tests/test_domain.py` | workflow, RBAC rules, duplicates, file validation, lockout/session rules, cosine/threshold/recommendation logic |
| `server/tests/test_override_offline.py` | administrator override approval and the 'panel approved offline' shortcut (RBAC, reason/reference required, audit, routing, setting) |
| `server/tests/test_api.py` | auth, RBAC & permission audit, TC-01…TC-12, submission/upload validation, full approval chain with archive + embedding, search/filters/pagination, reader (needs PyMuPDF), reports RBAC/CSV, admin, settings |
| `server/tests/test_real_model.py` | real MiniLM semantic check (skipped unless the model is installed) |
| `client/tests/test_api_client.py` | client error translation (no GUI) |
The API tests use a **test-only hash embedder** (`EMBEDDER=hash`) so they run offline; it is a bag-of-words toy, so TC-06 here verifies the pipeline (ranking, threshold, filters). True semantic quality is checked by `test_real_model.py`. Performance has not been measured yet; record results here after running on the target hardware.
