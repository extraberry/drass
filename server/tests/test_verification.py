"""Manuscript flow at API level: publication status visibility (FR10), companion files (FR15), admin boundaries (FR11/FR17),
backup and restore, username change."""
import os
from server.app.db import SessionLocal
from server.app.models import ResearchWork
from server.tests.conftest import STORAGE
from server.tests.helpers import *   # noqa: F401,F403
from server.tests.helpers import DEMO_PASSWORD, ZIP, verify


def _archived(client, status, title=None, companion=False):
    sh = login(client, "student1")
    wid = ready_submission(client, sh, **({"title": title} if title else {}))
    if companion:
        assert upload(client, sh, wid, kind="SOURCE_CODE", filename="src.zip", data=ZIP).status_code == 200
    assert client.post(f"/submissions/{wid}/submit", headers=sh).status_code == 200
    archive_chain(client, wid, publication_status=status)
    return wid


def _can_open(client, user, wid):
    return client.get(f"/repository/{wid}", headers=login(client, user)).status_code == 200


def _actions(client):
    return {i["action"] for i in client.get("/audit-logs?page_size=200", headers=login(client, "admin")).json()["items"]}


# ---------------- publication status decides who can see archived research ----------------
def test_public_research_is_visible_to_everyone_who_may_read_research(client):
    wid = _archived(client, "PUBLIC")
    for u in ("student2", "faculty1", "libstaff1", "headlibrarian", "external1"):
        assert _can_open(client, u, wid), u
    assert client.get(f"/public/repository/{wid}").status_code == 200


def test_restricted_research_hidden_from_external_users_and_guests(client):
    wid = _archived(client, "RESTRICTED", title="Restricted Study on Laboratory Access Control")
    for u in ("student2", "faculty1", "libstaff1", "headlibrarian"):
        assert _can_open(client, u, wid), u
    assert not _can_open(client, "external1", wid)
    assert client.get(f"/public/repository/{wid}").status_code == 404
    assert client.get("/repository", headers=login(client, "external1")).json()["total"] == 0
    r = client.post("/search/semantic", headers=login(client, "external1"), json={"query": "laboratory access control"}).json()
    assert r["count"] == 0


def test_unpublished_research_only_library_staff_and_owner(client):
    wid = _archived(client, "UNPUBLISHED", title="Unpublished Study on Thesis Embargo Handling")
    assert _can_open(client, "student1", wid) and _can_open(client, "libstaff1", wid) and _can_open(client, "headlibrarian", wid)
    for u in ("student2", "faculty1", "external1"):
        assert not _can_open(client, u, wid), u
    assert client.get("/repository", headers=login(client, "faculty1")).json()["total"] == 0
    assert client.get("/repository", headers=login(client, "student1")).json()["total"] == 1
    assert client.get(f"/reader/{wid}/info", headers=login(client, "student2")).status_code == 403


def test_library_staff_change_publication_status(client):
    wid = _archived(client, "PUBLIC")
    ls = login(client, "libstaff1")
    r = client.put(f"/repository/{wid}/publication", headers=ls, json={"publication_status": "UNPUBLISHED"})
    assert r.status_code == 200 and r.json()["publication_status"] == "UNPUBLISHED"
    assert not _can_open(client, "external1", wid)
    assert client.put(f"/repository/{wid}/publication", headers=ls, json={"publication_status": "SECRET"}).status_code == 422
    for u in ("student1", "faculty1", "external1", "admin"):
        assert client.put(f"/repository/{wid}/publication", headers=login(client, u), json={"publication_status": "PUBLIC"}).status_code == 403, u
    assert "PUBLICATION_STATUS_CHANGED" in _actions(client)


def test_publication_filter_is_for_library_staff_only(client):
    _archived(client, "PUBLIC", title="Public Study on Barangay Data Portals")
    _archived(client, "RESTRICTED", title="Restricted Study on Enrollment Analytics")
    ls = login(client, "libstaff1")
    assert client.get("/repository?publication_status=RESTRICTED", headers=ls).json()["total"] == 1
    assert client.get("/repository", headers=ls).json()["total"] == 2
    assert client.get("/repository?publication_status=RESTRICTED", headers=login(client, "student2")).json()["total"] == 2   # ignored


# ---------------- companion files ----------------
def test_companion_files_only_for_library_staff_and_owner(client):
    wid = _archived(client, "PUBLIC", title="Study With Source Code Companion File", companion=True)
    fid = next(f["file_id"] for f in client.get(f"/submissions/{wid}", headers=login(client, "student1")).json()["files"] if f["file_type"] == "SOURCE_CODE")
    url = f"/repository/{wid}/companions/{fid}"
    for u in ("student1", "libstaff1", "headlibrarian"):
        r = client.get(url, headers=login(client, u))
        assert r.status_code == 200 and r.content == ZIP, u
    for u in ("student2", "faculty1", "external1", "admin"):
        assert client.get(url, headers=login(client, u)).status_code == 403, u
    detail = lambda u: client.get(f"/repository/{wid}", headers=login(client, u)).json()["files"]
    assert any(f["file_type"] == "SOURCE_CODE" for f in detail("libstaff1"))
    assert all(f["file_type"] == "MANUSCRIPT" for f in detail("student2"))
    assert "COMPANION_FILE_OPENED" in _actions(client)


def test_manuscript_pdf_is_never_served_as_a_file(client):
    wid = _archived(client, "PUBLIC")
    fid = next(f["file_id"] for f in client.get(f"/submissions/{wid}", headers=login(client, "student1")).json()["files"])
    assert client.get(f"/repository/{wid}/companions/{fid}", headers=login(client, "libstaff1")).status_code == 404


# ---------------- Administrator boundaries ----------------
def test_admin_cannot_search_browse_or_read_research(client):
    wid = _archived(client, "PUBLIC")
    ah = login(client, "admin")
    assert client.get("/repository", headers=ah).status_code == 403
    assert client.get(f"/repository/{wid}", headers=ah).status_code == 403
    assert client.post("/search/semantic", headers=ah, json={"query": "attendance monitoring"}).status_code == 403
    assert client.get(f"/reader/{wid}/info", headers=ah).status_code == 403


def test_library_staff_cannot_use_admin_functions(client):
    for u in ("libstaff1", "headlibrarian"):
        h = login(client, u)
        for path in ("/users", "/audit-logs", "/activity-logs", "/admin/settings", "/admin/indexing", "/admin/backups", "/reports/archived", "/admin/roster"):
            assert client.get(path, headers=h).status_code == 403, (u, path)


def test_head_librarian_designation_is_set_by_the_admin(client):
    ah = login(client, "admin")
    users = {u["username"]: u for u in client.get("/users?page_size=100", headers=ah).json()["items"]}
    assert users["headlibrarian"]["is_head_librarian"] is True and users["libstaff1"]["is_head_librarian"] is False
    r = client.patch(f"/users/{users['libstaff1']['user_id']}", headers=ah, json={"is_head_librarian": True})
    assert r.status_code == 200 and r.json()["is_head_librarian"] is True
    r = client.patch(f"/users/{users['libstaff1']['user_id']}", headers=ah, json={"role": "FACULTY"})
    assert r.json()["is_head_librarian"] is False                           # the designation belongs to Library Staff only
    bad = client.post("/users", headers=ah, json={"username": "stud9", "password": "longenough1", "role": "STUDENT", "full_name": "S N",
                                                   "email": "s9@x.io", "is_head_librarian": True})
    assert bad.status_code == 200 and bad.json()["is_head_librarian"] is False


# ---------------- backup and restore (FR17, NFR6) ----------------
def test_backup_and_restore_round_trip(client):
    ah = login(client, "admin")
    wid = _archived(client, "PUBLIC", title="Study Present In The Backup Set")
    r = client.post("/admin/backups", headers=ah)
    assert r.status_code == 200 and r.json()["file_count"] >= 1
    name = r.json()["name"]
    assert any(b["name"] == name for b in client.get("/admin/backups", headers=ah).json()["items"])
    assert client.get("/admin/backups", headers=login(client, "student1")).status_code == 403
    for f in os.listdir(os.path.join(STORAGE, "manuscripts")):                    # simulate data loss
        os.remove(os.path.join(STORAGE, "manuscripts", f))
    with SessionLocal() as db:
        db.delete(db.get(ResearchWork, wid)); db.commit()
    assert client.post("/admin/backups/restore", headers=ah, json={"name": name, "confirm": "no"}).status_code == 422
    assert client.post("/admin/backups/restore", headers=ah, json={"name": "../etc", "confirm": "RESTORE"}).status_code == 422
    r = client.post("/admin/backups/restore", headers=ah, json={"name": name, "confirm": "RESTORE"})
    assert r.status_code == 200 and r.json()["safety_backup"].endswith("pre-restore")
    assert len(os.listdir(os.path.join(STORAGE, "manuscripts"))) == 1
    ah2 = login(client, "admin")
    assert "BACKUP_RESTORED" in {i["action"] for i in client.get("/audit-logs?page_size=200", headers=ah2).json()["items"]}


# ---------------- admin renames a username ----------------
def test_admin_can_change_username(client):
    ah = login(client, "admin")
    uid = next(u["user_id"] for u in client.get("/users?q=student1", headers=ah).json()["items"] if u["username"] == "student1")
    old_h = login(client, "student1")
    assert client.patch(f"/users/{uid}", headers=ah, json={"username": "student1.new"}).status_code == 200
    assert client.post("/auth/login", json={"username": "student1", "password": DEMO_PASSWORD}).status_code in (401, 403)
    assert client.get("/auth/me", headers=old_h).status_code == 401
    login(client, "student1.new")
    assert "USERNAME_CHANGED" in _actions(client)


def test_username_change_rejects_duplicates_and_non_admin(client):
    ah = login(client, "admin")
    uid = next(u["user_id"] for u in client.get("/users?q=student1", headers=ah).json()["items"] if u["username"] == "student1")
    assert client.patch(f"/users/{uid}", headers=ah, json={"username": "student2"}).status_code == 409
    assert client.patch(f"/users/{uid}", headers=ah, json={"username": "ab"}).status_code == 422
    assert client.patch(f"/users/{uid}", headers=login(client, "student2"), json={"username": "hacker"}).status_code == 403


# ---------------- submission notifications ----------------
def test_head_librarian_is_notified_and_student_hears_back(client):
    sh = login(client, "student1")
    wid = ready_submission(client, sh)
    client.post(f"/submissions/{wid}/submit", headers=sh)
    hl = login(client, "headlibrarian")
    assert any("verification" in n["title"].lower() or "verification" in n["message"].lower()
               for n in client.get("/notifications", headers=hl).json()["items"])
    verify(client, hl, wid, "RETURN", remarks="Sheet incomplete", sheet_complete=False)
    assert any("Sheet incomplete" in n["message"] or "returned" in n["title"].lower()
               for n in client.get("/notifications", headers=sh).json()["items"])
