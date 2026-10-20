# Integrating with DRASS (integration-ready design)
DRASS is **integration-ready; no third-party integrations are bundled** (capstone scope). External systems use a small, versioned HTTP API under `/api/v1`, authenticated by an **API key**. The desktop client's own routes are internal and may change; `/api/v1/*` is the stable contract.

## 1. Create a key (ADMIN)
Desktop client → **Integrations (API keys) → Create API key**. Name the system, choose scopes, set an expiry. The key (`drass_…`) is shown **once**; DRASS stores only its SHA-256 hash. Revoke at any time. Every create/revoke/rejected attempt is in the audit log (`API_KEY_CREATED`, `API_KEY_REVOKED`, `API_KEY_REJECTED`).

| Scope | Allows |
|---|---|
| `roster:write` | Sync the student roster (`POST /api/v1/integration/roster`) |
| `catalog:read` | Read metadata of **archived** research (no manuscripts, no files, no student numbers) |

Keys cannot call any user or admin route (they are not accounts). Limits: 300 requests/min per key; repeated bad keys from one IP are blocked briefly.

## 2. Endpoints (header `X-API-Key: drass_…`)
- `GET /api/v1/ping` — no key; returns `{"service":"DRASS","api_version":"v1"}`.
- `POST /api/v1/integration/roster` — body `{"students":[{"student_number":"2025-0001","last_name":"Navarro","first_name":"Ivy","department":"College of Education","status":"ACTIVE"}]}`. Idempotent upsert (max 5000 per call); `status` may be `INACTIVE` for graduated/withdrawn students (they can no longer self-register). Returns `{added, updated, unchanged, errors[]}`.
- `GET /api/v1/catalog/works?archived_since=2026-01-01&page=1&page_size=50&format=json|dc` — paged metadata; `format=dc` returns Dublin Core XML (header `X-Total-Count`) for library harvesters.
- `GET /api/v1/catalog/works/{id}` — one archived record (404 for anything not archived).

## 3. Examples
```
curl -H "X-API-Key: drass_XXXX" "http://SERVER:8000/api/v1/catalog/works?page_size=10"
curl -X POST -H "X-API-Key: drass_XXXX" -H "Content-Type: application/json" \
     -d "{\"students\":[{\"student_number\":\"2025-0001\",\"last_name\":\"Navarro\",\"first_name\":\"Ivy\"}]}" \
     http://SERVER:8000/api/v1/integration/roster
```
Python: `requests.get(url, headers={"X-API-Key": key}).json()`.

## 4. Security notes
Use the campus LAN/VPN or put DRASS behind HTTPS (keys travel in a header). One key per external system; use the shortest expiry that works. Metadata can still reveal unpublished abstracts only after archiving — nothing un-archived is ever exposed. Review the Data Privacy Act implications before sending data to any outside service. Not implemented: webhooks, single sign-on, email notifications, OAI-PMH protocol (the Dublin Core export is a plain XML list).
