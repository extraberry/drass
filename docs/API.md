# API (all errors: `{"success": false, "error_code": "...", "message": "...", "fields": {...}}`)
Auth: `POST /auth/login`, `POST /auth/logout`, `GET|PATCH /auth/me`, `POST /auth/change-password`. Bearer token in `Authorization`.
Lookups/dashboard/notifications: `GET /lookups`, `GET /dashboard`, `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all`.
Submissions (STUDENT): `GET|POST /submissions`, `GET|PATCH /submissions/{id}`, `PUT /submissions/{id}/files/{MANUSCRIPT|SOURCE_CODE|VIDEO|OTHER_COMPANION}?filename=` (raw body), `POST /submissions/{id}/submit|resubmit`, `POST /submissions/{id}/panel` (ADVISER/ADMIN).
Reviews: `GET /reviews/queue|history`, `GET /reviews/{assignment_id}`, `POST /reviews/{assignment_id}/approve|return|reject`.
Repository: `GET /repository` (filters program_id, department_id, year, adviser_id, category_id, author, keyword; sort; page; page_size), `GET|PATCH /repository/{id}`.
Search: `POST /search/semantic`, `GET /recommendations/{id}`. Reader: `GET /reader/{id}/info`, `GET /reader/{id}/pages/{n}?scale=`.
Reports: `GET /reports/{submissions|approvals|rejections|pending-reviews|archived|user-activity|system-activity}?format=csv`.
Admin: `GET|POST /users`, `PATCH /users/{id}`, `POST /users/{id}/activate|deactivate|reset-password`, `GET|PUT /admin/settings`, `GET|POST|PATCH /admin/lookups/{departments|programs|categories}`, `GET /admin/roles`, `GET /admin/indexing`, `POST /admin/indexing/rebuild`, `GET /audit-logs`, `GET /activity-logs`. Interactive docs at `/docs` when `ENABLE_DOCS=true`.

**Public (no login):** `GET /public/lookups`, `GET /public/repository`, `GET /public/repository/{id}`, `POST /public/search/semantic`, `GET /public/recommendations/{id}` — ARCHIVED records only, rate-limited. `POST /auth/register-student` (student_number, last_name, username, email, password).
**Roster (ADMIN):** `GET|POST /admin/roster`, `POST /admin/roster/import` (`{"csv": "student_number,last_name,first_name,department\n..."}`).

**Integration API (X-API-Key, stable):** `GET /api/v1/ping`, `POST /api/v1/integration/roster`, `GET /api/v1/catalog/works`, `GET /api/v1/catalog/works/{id}` — see `docs/INTEGRATION.md`. **Key admin (ADMIN):** `GET|POST /admin/api-keys`, `POST /admin/api-keys/{id}/revoke`.

**Added**: `POST /reviews/{assignment_id}/approve` accepts optional `panel_offline` (bool) and `panel_offline_reference` (required when `panel_offline`; adviser stage only). `POST /admin/works/{work_id}/override-approve` body `{mode: "next"|"archive", reason, expected_version?}` (ADMIN). New setting `offline_panel_skips_dean`.
