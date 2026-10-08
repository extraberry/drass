# API (all errors: `{"success": false, "error_code": "...", "message": "...", "fields": {...}}`)
Auth: `POST /auth/login`, `POST /auth/logout`, `GET|PATCH /auth/me`, `POST /auth/change-password`. Bearer token in `Authorization`.
Lookups/dashboard/notifications: `GET /lookups`, `GET /dashboard`, `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all`.
Submissions (STUDENT): `GET|POST /submissions`, `GET|PATCH /submissions/{id}`, `PUT /submissions/{id}/files/{MANUSCRIPT|SOURCE_CODE|VIDEO|OTHER_COMPANION}?filename=` (raw body), `POST /submissions/{id}/submit|resubmit`, `POST /submissions/{id}/panel` (ADVISER/ADMIN).
Reviews: `GET /reviews/queue|history`, `GET /reviews/{assignment_id}`, `POST /reviews/{assignment_id}/approve|return|reject`.
Repository: `GET /repository` (filters program_id, department_id, year, adviser_id, category_id, author, keyword; sort; page; page_size), `GET|PATCH /repository/{id}`.
Search: `POST /search/semantic`, `GET /recommendations/{id}`. Reader: `GET /reader/{id}/info`, `GET /reader/{id}/pages/{n}?scale=`.
Reports: `GET /reports/{submissions|approvals|rejections|pending-reviews|archived|user-activity|system-activity}?format=csv`.
Admin: `GET|POST /users`, `PATCH /users/{id}`, `POST /users/{id}/activate|deactivate|reset-password`, `GET|PUT /admin/settings`, `GET|POST|PATCH /admin/lookups/{departments|programs|categories}`, `GET /admin/roles`, `GET /admin/indexing`, `POST /admin/indexing/rebuild`, `GET /audit-logs`, `GET /activity-logs`. Interactive docs at `/docs` when `ENABLE_DOCS=true`.
