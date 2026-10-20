from server.tests.helpers import login, ready_submission, archive_chain


def make_key(client, scopes=("catalog:read",), name="Library catalog", **extra):
    r = client.post("/admin/api-keys", headers=login(client, "admin"), json={"name": name, "scopes": list(scopes), **extra})
    assert r.status_code == 200, r.text
    return r.json()


def K(key):
    return {"X-API-Key": key["api_key"]}


def test_ping_is_public_and_versioned(client):
    assert client.get("/api/v1/ping").json()["api_version"] == "v1"


def test_only_admin_manages_keys_and_key_shown_once(client):
    assert client.post("/admin/api-keys", headers=login(client, "student1"), json={"name": "x" * 5, "scopes": ["catalog:read"]}).status_code == 403
    assert client.get("/admin/api-keys").status_code == 401
    k = make_key(client)
    assert k["api_key"].startswith("drass_")
    listing = client.get("/admin/api-keys", headers=login(client, "admin")).json()["items"]
    assert listing[0]["key_prefix"] == k["api_key"][:12] and "api_key" not in listing[0] and k["api_key"] not in str(listing)


def test_invalid_scope_rejected(client):
    r = client.post("/admin/api-keys", headers=login(client, "admin"), json={"name": "Bad scope", "scopes": ["users:delete"]})
    assert r.status_code == 422


def test_catalog_requires_valid_key(demo):
    assert demo.get("/api/v1/catalog/works").status_code == 401
    assert demo.get("/api/v1/catalog/works", headers={"X-API-Key": "drass_wrong"}).status_code == 401
    assert demo.get("/api/v1/catalog/works", headers={"X-API-Key": "not-even-prefixed"}).status_code == 401
    acts = [a["action"] for a in demo.get("/audit-logs?page_size=200", headers=login(demo, "admin")).json()["items"]]
    assert "API_KEY_REJECTED" in acts and "API_KEY_CREATED" not in acts


def test_catalog_returns_only_archived_metadata(demo):
    sh = login(demo, "student1")
    wid = ready_submission(demo, sh)                       # an un-archived work must never appear
    demo.post(f"/submissions/{wid}/submit", headers=sh)
    k = make_key(demo)
    r = demo.get("/api/v1/catalog/works?page_size=5", headers=K(k)).json()
    assert r["total"] == 12 and len(r["items"]) == 5
    item = r["items"][0]
    assert set(item) == {"id", "reference_no", "title", "abstract", "year", "authors", "program", "department", "category", "adviser", "keywords", "archived_at"}
    assert all(isinstance(a, str) for a in item["authors"])             # names only, no student numbers
    text = str(r).lower()
    assert "storage" not in text and "sha256" not in text and "student_number" not in text
    assert demo.get(f"/api/v1/catalog/works/{wid}", headers=K(k)).status_code == 404
    one = demo.get(f"/api/v1/catalog/works/{item['id']}", headers=K(k))
    assert one.status_code == 200 and one.json()["title"] == item["title"]


def test_catalog_filters_and_validation(demo):
    k = make_key(demo)
    assert demo.get("/api/v1/catalog/works?archived_since=2999-01-01", headers=K(k)).json()["total"] == 0
    assert demo.get("/api/v1/catalog/works?archived_since=2000-01-01", headers=K(k)).json()["total"] == 12
    assert demo.get("/api/v1/catalog/works?archived_since=garbage", headers=K(k)).status_code == 422
    assert demo.get("/api/v1/catalog/works?page_size=1000", headers=K(k)).status_code == 422
    assert demo.get("/api/v1/catalog/works?format=csv", headers=K(k)).status_code == 422


def test_catalog_dublin_core_xml(demo):
    k = make_key(demo)
    r = demo.get("/api/v1/catalog/works?format=dc&page_size=3", headers=K(k))
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    assert r.text.count("<record>") == 3 and "<dc:title>" in r.text and "Mary the Queen College" in r.text
    assert r.headers["x-total-count"] == "12"


def test_scope_is_enforced(demo):
    k = make_key(demo, scopes=("catalog:read",))
    r = demo.post("/api/v1/integration/roster", headers=K(k), json={"students": []})
    assert r.status_code == 403
    k2 = make_key(demo, scopes=("roster:write",), name="Registrar sync")
    assert demo.get("/api/v1/catalog/works", headers=K(k2)).status_code == 403


def test_api_key_cannot_reach_user_or_admin_routes(client):
    k = make_key(client, scopes=("catalog:read", "roster:write"))
    for path in ("/users", "/audit-logs", "/admin/roster", "/admin/api-keys", "/repository"):
        assert client.get(path, headers=K(k)).status_code == 401, path
    assert client.get("/admin/api-keys", headers={"Authorization": "Bearer " + k["api_key"]}).status_code == 401


def test_revoked_and_expired_keys_rejected(client):
    admin = login(client, "admin")
    k = make_key(client)
    assert client.get("/api/v1/catalog/works", headers=K(k)).status_code == 200
    assert client.post(f"/admin/api-keys/{k['key_id']}/revoke", headers=admin).status_code == 200
    assert client.get("/api/v1/catalog/works", headers=K(k)).status_code == 401
    from server.app.db import SessionLocal
    from server.app.models import ApiKey
    from datetime import timedelta
    from server.app.core.timeutil import utcnow
    k2 = make_key(client, name="Short lived", expires_days=1)
    with SessionLocal() as db:
        row = db.get(ApiKey, k2["key_id"]); row.expires_at = utcnow() - timedelta(seconds=1); db.commit()
    assert client.get("/api/v1/catalog/works", headers=K(k2)).status_code == 401


def test_last_used_is_recorded(client):
    k = make_key(client)
    assert client.get("/admin/api-keys", headers=login(client, "admin")).json()["items"][0]["last_used_at"] is None
    client.get("/api/v1/catalog/works", headers=K(k))
    assert client.get("/admin/api-keys", headers=login(client, "admin")).json()["items"][0]["last_used_at"]


def test_roster_sync_adds_updates_and_enables_registration(client):
    k = make_key(client, scopes=("roster:write",), name="Registrar sync")
    body = {"students": [{"student_number": "2025-0001", "last_name": "Navarro", "first_name": "Ivy", "department": "College of Education"},
                         {"student_number": "2023-0101", "last_name": "Reyes-Cruz", "first_name": "Carla"},      # existing: update
                         {"student_number": "bad id!", "last_name": "X", "first_name": "Y"},
                         {"student_number": "2025-0001", "last_name": "Dup", "first_name": "Dup"}]}
    r = client.post("/api/v1/integration/roster", headers=K(k), json=body).json()
    assert r["added"] == 1 and r["updated"] == 1 and len(r["errors"]) == 2
    again = client.post("/api/v1/integration/roster", headers=K(k), json={"students": body["students"][:2]}).json()
    assert again["added"] == 0 and again["updated"] == 0 and again["unchanged"] == 2        # idempotent
    reg = client.post("/auth/register-student", json={"student_number": "2025-0001", "last_name": "Navarro", "username": "ivy", "email": "ivy@x.io", "password": "longenough1"})
    assert reg.status_code == 200
    reg2 = client.post("/auth/register-student", json={"student_number": "2023-0101", "last_name": "Reyes-Cruz", "username": "carla", "email": "c@x.io", "password": "longenough1"})
    assert reg2.status_code == 200
    acts = [a["action"] for a in client.get("/audit-logs?page_size=200", headers=login(client, "admin")).json()["items"]]
    assert "ROSTER_SYNCED" in acts


def test_roster_sync_can_deactivate_student(client):
    k = make_key(client, scopes=("roster:write",), name="Registrar sync")
    client.post("/api/v1/integration/roster", headers=K(k), json={"students": [{"student_number": "2023-0102", "last_name": "Tan", "first_name": "Daniel", "status": "INACTIVE"}]})
    r = client.post("/auth/register-student", json={"student_number": "2023-0102", "last_name": "Tan", "username": "dan", "email": "d@x.io", "password": "longenough1"})
    assert r.status_code == 422                                                              # inactive students cannot register


def test_failed_key_attempts_are_rate_limited(client):
    codes = [client.get("/api/v1/catalog/works", headers={"X-API-Key": "drass_nope"}).status_code for _ in range(32)]
    assert codes[0] == 401 and codes[-1] == 429
