from server.tests.helpers import DEMO_PASSWORD, login, new_draft, ready_submission

REG = {"student_number": "2023-0101", "last_name": "Reyes", "username": "carla", "email": "carla@school.edu", "password": "longenough1"}


# ---------------- guest access (no login) ----------------
def test_guest_can_browse_and_search_without_login(demo):
    r = demo.get("/public/repository?page_size=5")
    assert r.status_code == 200 and r.json()["total"] == 12
    assert demo.get("/public/repository?keyword=dengue").json()["total"] == 1
    s = demo.post("/public/search/semantic", json={"query": "volcanic eruption lava geology"})
    assert s.status_code == 200 and s.json()["count"] == 0
    assert demo.get("/public/lookups").json()["categories"]


def test_guest_search_returns_ranked_results(demo):
    demo.put("/admin/settings", headers=login(demo, "admin"), json={"values": {"semantic_threshold": "0.1"}})
    r = demo.post("/public/search/semantic", json={"query": "research projects that use technology to improve student learning"}).json()
    assert r["count"] >= 1 and r["results"][0]["title"].startswith("Gamified")


def test_guest_detail_has_no_read_access_or_files(demo):
    wid = demo.get("/public/repository").json()["items"][0]["work_id"]
    d = demo.get(f"/public/repository/{wid}").json()
    assert d["can_read"] is False and "files" not in d and "storage" not in str(d).lower()
    assert demo.get(f"/reader/{wid}/pages/1").status_code == 401        # manuscripts need sign-in
    assert demo.get(f"/public/recommendations/{wid}").status_code == 200


def test_guest_cannot_see_unarchived_work(client):
    wid = ready_submission(client, login(client, "student1"))
    assert client.get(f"/public/repository/{wid}").status_code == 404    # same answer as a missing record
    assert client.get(f"/public/repository/99999").status_code == 404
    assert client.get(f"/public/recommendations/{wid}").status_code == 404
    assert client.get("/public/repository").json()["total"] == 0


def test_guest_cannot_use_protected_routes(client):
    for path in ("/reviews/queue", "/submissions", "/users", "/audit-logs", "/repository", "/dashboard", "/lookups"):
        assert client.get(path).status_code == 401, path


def test_guest_search_is_rate_limited(client):
    codes = [client.post("/public/search/semantic", json={"query": "anything goes here"}).status_code for _ in range(32)]
    assert codes[0] == 200 and codes[-1] == 429


# ---------------- student registration ----------------
def test_student_can_register_and_login(client):
    r = client.post("/auth/register-student", json=REG)
    assert r.status_code == 200 and r.json()["success"] is True
    h = login(client, "carla", "longenough1")
    me = client.get("/auth/me", headers=h).json()
    assert me["role"] == "STUDENT" and me["full_name"] == "Carla Reyes" and me["student_number"] == "2023-0101"
    assert client.get("/submissions", headers=h).status_code == 200
    assert client.get("/reviews/queue", headers=h).status_code == 403
    acts = [a["action"] for a in client.get("/audit-logs?page_size=200", headers=login(client, "admin")).json()["items"]]
    assert "STUDENT_REGISTERED" in acts


def test_registration_is_case_and_format_tolerant(client):
    r = client.post("/auth/register-student", json={**REG, "student_number": "2023-0101", "last_name": " REYES "})
    assert r.status_code == 200


def test_registration_requires_roster_id_and_matching_surname(client):
    a = client.post("/auth/register-student", json={**REG, "last_name": "Wrongname"})
    b = client.post("/auth/register-student", json={**REG, "student_number": "9999-9999"})
    assert a.status_code == b.status_code == 422
    assert a.json()["message"] == b.json()["message"]                    # no hint which part failed
    assert client.post("/auth/login", json={"username": "carla", "password": "longenough1"}).status_code == 401


def test_one_student_one_account(client):
    assert client.post("/auth/register-student", json=REG).status_code == 200
    again = client.post("/auth/register-student", json={**REG, "username": "carla2", "email": "other@school.edu"})
    assert again.status_code == 409 and again.json()["error_code"] == "CONFLICT"
    seeded = client.post("/auth/register-student", json={**REG, "student_number": "2022-0001", "last_name": "Ramos",
                                                         "username": "sofia2", "email": "s2@school.edu"})
    assert seeded.status_code == 409                                     # student1 already owns 2022-0001


def test_registration_validation(client):
    assert client.post("/auth/register-student", json={**REG, "password": "short"}).status_code == 422
    assert client.post("/auth/register-student", json={**REG, "username": "admin"}).json()["fields"]["username"]
    assert client.post("/auth/register-student", json={**REG, "email": "student1@demo.drass.local"}).json()["fields"]["email"]
    assert client.post("/auth/register-student", json={**REG, "email": "not-an-email"}).status_code == 422


def test_registration_always_creates_student_role(client):
    client.post("/auth/register-student", json={**REG, "role": "ADMIN"})   # extra field must be ignored
    assert client.get("/auth/me", headers=login(client, "carla", "longenough1")).json()["role"] == "STUDENT"


def test_registration_rate_limited(client):
    codes = [client.post("/auth/register-student", json={**REG, "student_number": "0000-0000"}).status_code for _ in range(12)]
    assert codes[0] == 422 and codes[-1] == 429


def test_admin_admin_cannot_duplicate_student_number(client):
    a = login(client, "admin")
    r = client.post("/users", headers=a, json={"username": "dup", "password": "longenough1", "role": "STUDENT", "full_name": "D D",
                                               "email": "dup@x.io", "student_number": "2022-0001"})
    assert r.status_code == 409


# ---------------- roster administration ----------------
def test_roster_admin_only_and_csv_import(client):
    assert client.get("/admin/roster", headers=login(client, "student1")).status_code == 403
    assert client.get("/admin/roster").status_code == 401
    a = login(client, "admin")
    csv = "student_number,last_name,first_name,department\n2024-0001,Mendoza,Lia,College of Information Technology\n2023-0101,Reyes,Carla,\nbad id!,X,Y,\n"
    r = client.post("/admin/roster/import", headers=a, json={"csv": csv}).json()
    assert r["added"] == 1 and r["skipped"] == 1 and len(r["errors"]) == 1
    assert client.post("/admin/roster/import", headers=a, json={"csv": "a,b\n1,2"}).status_code == 422
    reg = client.post("/auth/register-student", json={**REG, "student_number": "2024-0001", "last_name": "Mendoza", "username": "lia", "email": "lia@x.io"})
    assert reg.status_code == 200
    rows = client.get("/admin/roster?q=2024", headers=a).json()
    assert rows["items"][0]["account"] == "Registered"
    assert client.post("/admin/roster", headers=a, json={"student_number": "2024-0001", "last_name": "A", "first_name": "B"}).status_code == 409
