import os
import pytest
from server.app.db import SessionLocal
from server.app.models import AuditLog, Embedding, ResearchWork
from server.app.services import index_service
from server.tests.conftest import STORAGE
from server.tests.helpers import *   # noqa: F401,F403
from server.tests.helpers import DEMO_PASSWORD, PDF, ZIP, verify


def audit_actions(client):
    h = login(client, "admin")
    return client.get("/audit-logs?page_size=200", headers=h).json()["items"]


# ---------------- authentication ----------------
def test_login_logout_and_session(client):
    h = login(client, "student1")
    assert client.get("/auth/me", headers=h).json()["role"] == "STUDENT"
    assert client.post("/auth/logout", headers=h).status_code == 200
    r = client.get("/auth/me", headers=h)
    assert r.status_code == 401 and r.json()["error_code"] == "SESSION_EXPIRED"


def test_invalid_session_rejected(client):
    assert client.get("/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/auth/me").status_code == 401


def test_generic_login_error(client):
    a = client.post("/auth/login", json={"username": "ghost", "password": "xxxxxxxx"})
    b = client.post("/auth/login", json={"username": "student1", "password": "wrong-password"})
    assert a.status_code == b.status_code == 401
    assert a.json()["message"] == b.json()["message"] == "Invalid username or password."


def test_lockout_after_five_failures(client):
    for _ in range(5):
        client.post("/auth/login", json={"username": "student2", "password": "bad-password"})
    r = client.post("/auth/login", json={"username": "student2", "password": DEMO_PASSWORD})
    assert r.status_code == 423 and r.json()["error_code"] == "ACCOUNT_LOCKED"


def test_tc10_deactivated_user_cannot_login(client):
    admin = login(client, "admin")
    uid = next(u["user_id"] for u in client.get("/users", headers=admin).json()["items"] if u["username"] == "student2")
    assert client.post(f"/users/{uid}/deactivate", headers=admin).status_code == 200
    r = client.post("/auth/login", json={"username": "student2", "password": DEMO_PASSWORD})
    assert r.status_code == 403 and r.json()["error_code"] == "ACCOUNT_DISABLED"


# ---------------- RBAC ----------------
def test_tc09_external_denied_verification_queue_and_audited(client):
    h = login(client, "external1")
    r = client.get("/verifications/queue", headers=h)
    assert r.status_code == 403 and r.json()["error_code"] == "FORBIDDEN"
    assert any(a["action"] == "PERMISSION_DENIED" and a["user"] == "external1" for a in audit_actions(client))


def test_student_cannot_manage_users_or_view_audit(client):
    h = login(client, "student1")
    assert client.get("/users", headers=h).status_code == 403
    assert client.get("/audit-logs", headers=h).status_code == 403
    assert client.get("/admin/indexing", headers=h).status_code == 403


def test_external_cannot_submit(client):
    assert client.post("/submissions", headers=login(client, "external1"), json={"title": "x"}).status_code == 403


def test_student_cannot_verify(client):
    h = login(client, "student1")
    wid = ready_submission(client, h)
    assert client.post("/submissions/%d/submit" % wid, headers=h).status_code == 200
    assert verify(client, h, wid).status_code == 403


def test_other_student_cannot_see_private_submission(client):
    wid = new_draft(client, login(client, "student1"))
    h2 = login(client, "student2")
    assert client.get(f"/submissions/{wid}", headers=h2).status_code == 403
    assert client.get(f"/repository/{wid}", headers=h2).status_code == 403
    assert client.get(f"/reader/{wid}/pages/1", headers=h2).status_code == 403


# ---------------- submission ----------------
def test_tc01_missing_abstract_blocked(client):
    h = login(client, "student1")
    wid = ready_submission(client, h, abstract="")
    r = client.post(f"/submissions/{wid}/submit", headers=h)
    assert r.status_code == 422 and "abstract" in r.json()["fields"]
    assert client.get(f"/submissions/{wid}", headers=h).json()["status"] == "DRAFT"


def test_manuscript_required(client):
    h = login(client, "student1")
    wid = new_draft(client, h)
    r = client.post(f"/submissions/{wid}/submit", headers=h)
    assert r.status_code == 422 and "manuscript" in r.json()["fields"]


def test_tc02_duplicate_blocked(client):
    h1, h2 = login(client, "student1"), login(client, "student2")
    a = ready_submission(client, h1, title="Duplicate Test Title", authors=["Ana Cruz", "Ben Lee"])
    assert client.post(f"/submissions/{a}/submit", headers=h1).status_code == 200
    b = ready_submission(client, h2, title="duplicate  test title!", authors=["ben lee", "ANA CRUZ"])
    r = client.post(f"/submissions/{b}/submit", headers=h2)
    assert r.status_code == 409 and r.json()["error_code"] == "DUPLICATE_RESEARCH"
    assert client.get(f"/submissions/{b}", headers=h2).json()["status"] == "DRAFT"


def test_upload_validation(client):
    h = login(client, "student1")
    wid = new_draft(client, h)
    assert upload(client, h, wid, data=b"MZ not a pdf").status_code == 422          # signature
    assert upload(client, h, wid, filename="x.exe").status_code == 422               # extension
    assert upload(client, h, wid, kind="SOURCE_CODE", filename="src.pdf", data=PDF).status_code == 422
    assert upload(client, h, wid, kind="SOURCE_CODE", filename="src.zip", data=ZIP).status_code == 200
    assert os.listdir(os.path.join(STORAGE, "temp")) == []                            # temp cleaned up


def test_upload_size_limit_configurable(client):
    admin = login(client, "admin")
    assert client.put("/admin/settings", headers=admin, json={"values": {"max_manuscript_mb": "1"}}).status_code == 200
    h = login(client, "student1")
    wid = new_draft(client, h)
    r = upload(client, h, wid, data=b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10))
    assert r.status_code == 422
    assert os.listdir(os.path.join(STORAGE, "temp")) == []


def test_filename_sanitized_and_internal_name_is_uuid(client):
    h = login(client, "student1")
    wid = new_draft(client, h)
    r = upload(client, h, wid, filename="../../evil.pdf")
    assert r.status_code == 200 and r.json()["filename"] == "evil.pdf"
    files = os.listdir(os.path.join(STORAGE, "manuscripts"))
    assert len(files) == 1 and "evil" not in files[0]
    detail = client.get(f"/submissions/{wid}", headers=h).json()
    assert "storage_path" not in str(detail) and "stored_filename" not in str(detail)


def test_replace_manuscript_keeps_single_active(client):
    h = login(client, "student1")
    wid = new_draft(client, h)
    upload(client, h, wid); upload(client, h, wid)
    d = client.get(f"/submissions/{wid}", headers=h).json()
    assert len([f for f in d["files"] if f["file_type"] == "MANUSCRIPT"]) == 1
    assert any(a["action"] == "FILE_REPLACED" for a in audit_actions(client))


# ---------------- workflow (manuscript: Pending Verification -> Returned / Archived) ----------------
def _pending(client, **kw):
    sh = login(client, "student1")
    wid = ready_submission(client, sh, **kw)
    r = client.post(f"/submissions/{wid}/submit", headers=sh)
    assert r.status_code == 200 and r.json()["status"] == "PENDING_VERIFICATION", r.text
    return sh, wid


def test_tc03_verification_archives_and_records_the_approver(client):
    sh, wid = _pending(client)
    archive_chain(client, wid)
    d = client.get(f"/submissions/{wid}", headers=sh).json()
    assert d["status"] == "ARCHIVED" and d["archived_at"] and d["publication_status"] == "PUBLIC"
    assert d["archived_by"] == "Lorenzo Santos"
    assert [h["result"] for h in d["verification_history"]] == ["APPROVE"]
    assert all(d["verification_history"][0]["checklist"].values())
    with SessionLocal() as db:
        assert db.query(Embedding).filter_by(work_id=wid, status="COMPLETE").count() == 1
    assert any(a["action"] == "RESEARCH_ARCHIVED" for a in audit_actions(client))


def test_only_the_head_librarian_can_verify(client):
    _, wid = _pending(client)
    assert verify(client, login(client, "libstaff1"), wid).status_code == 403          # Library Staff, not the head
    for u in ("faculty1", "student2", "external1", "admin"):
        assert verify(client, login(client, u), wid).status_code == 403, u
    assert client.get(f"/submissions/{wid}", headers=login(client, "student1")).json()["status"] == "PENDING_VERIFICATION"


def test_library_staff_can_see_the_queue_but_not_act(client):
    _, wid = _pending(client)
    r = client.get("/verifications/queue", headers=login(client, "libstaff1")).json()
    assert [i["work_id"] for i in r["items"]] == [wid] and r["can_verify"] is False
    assert client.get("/verifications/queue", headers=login(client, "headlibrarian")).json()["can_verify"] is True
    assert client.get("/verifications/queue", headers=login(client, "admin")).status_code == 403


def test_incomplete_checklist_cannot_be_approved(client):
    sh, wid = _pending(client)
    hl = login(client, "headlibrarian")
    r = verify(client, hl, wid, "APPROVE", dean_signed=False)
    assert r.status_code == 422
    assert client.get(f"/submissions/{wid}", headers=sh).json()["status"] == "PENDING_VERIFICATION"


def test_tc04_return_with_remarks_then_resubmit_then_archive(client):
    sh, hl = login(client, "student1"), login(client, "headlibrarian")
    wid = ready_submission(client, sh)
    client.post(f"/submissions/{wid}/submit", headers=sh)
    assert verify(client, hl, wid, "RETURN", remarks="").status_code == 422             # remarks required
    r = verify(client, hl, wid, "RETURN", remarks="Dean's signature is missing", dean_signed=False)
    assert r.status_code == 200 and r.json()["status"] == "RETURNED"
    d = client.get(f"/submissions/{wid}", headers=sh).json()
    assert d["verification_history"][0]["remarks"] == "Dean's signature is missing"
    assert d["verification_history"][0]["checklist"]["dean_signed"] is False
    assert client.post(f"/submissions/{wid}/resubmit", headers=sh, json={"change_notes": " "}).status_code == 422
    assert upload(client, sh, wid).status_code == 200                                    # corrected final PDF
    r = client.post(f"/submissions/{wid}/resubmit", headers=sh, json={"change_notes": "Added the dean's signature"})
    assert r.status_code == 200 and r.json()["status"] == "PENDING_VERIFICATION"
    d = client.get(f"/submissions/{wid}", headers=sh).json()
    assert [x["revision_number"] for x in d["revisions"]] == [1, 2]
    assert len(d["verification_history"]) == 1                                           # earlier verification preserved
    archive_chain(client, wid)


def test_there_is_no_reject_and_no_in_system_adviser_review(client):
    _, wid = _pending(client)
    hl = login(client, "headlibrarian")
    assert client.post(f"/verifications/{wid}", headers=hl, json={"decision": "REJECT", "remarks": "no"}).status_code == 422
    assert client.get("/reviews/queue", headers=login(client, "faculty1")).status_code == 404
    assert client.post(f"/admin/works/{wid}/override-approve", headers=login(client, "admin"), json={}).status_code in (404, 405)


def test_stale_version_rejected(client):
    _, wid = _pending(client)
    r = verify(client, login(client, "headlibrarian"), wid, expected_version=999)
    assert r.status_code == 409 and r.json()["error_code"] == "STALE_STATE"


def test_cannot_resubmit_non_returned_or_submit_twice(client):
    sh, wid = _pending(client)
    assert client.post(f"/submissions/{wid}/submit", headers=sh).status_code == 409
    assert client.post(f"/submissions/{wid}/resubmit", headers=sh, json={"change_notes": "x"}).status_code == 409
    assert client.patch(f"/submissions/{wid}", headers=sh, json={"title": "Edited"}).status_code == 409


def test_adviser_and_dean_are_required_and_must_be_faculty(client):
    sh = login(client, "student1")
    wid = ready_submission(client, sh)
    lk = lookups(client, sh)
    assert client.patch(f"/submissions/{wid}", headers=sh, json={"dean_id": None}).status_code in (200, 422)
    admin_id = next(u["user_id"] for u in client.get("/users", headers=login(client, "admin")).json()["items"] if u["username"] == "admin")
    r = client.patch(f"/submissions/{wid}", headers=sh, json={"dean_id": admin_id})
    assert r.status_code == 422 and "dean_id" in r.json()["fields"]
    assert lk["faculty"] and all(f["id"] != admin_id for f in lk["faculty"])


def test_category_is_optional(client):
    sh = login(client, "student1")
    wid = ready_submission(client, sh)
    assert client.get(f"/submissions/{wid}", headers=sh).json()["category_id"] is None
    assert client.post(f"/submissions/{wid}/submit", headers=sh).status_code == 200


def test_archive_blocked_when_manuscript_missing(client):
    sh, wid = _pending(client)
    for f in os.listdir(os.path.join(STORAGE, "manuscripts")):
        os.remove(os.path.join(STORAGE, "manuscripts", f))
    r = verify(client, login(client, "headlibrarian"), wid)                              # archiving is blocked (NFR2)
    assert r.status_code == 500 and r.json()["error_code"] == "STORAGE_ERROR"
    assert client.get(f"/submissions/{wid}", headers=sh).json()["status"] == "PENDING_VERIFICATION"
    assert any(a["action"] == "ARCHIVE_FAILED" for a in audit_actions(client))


def test_roles_are_the_five_manuscript_roles(client):
    ah = login(client, "admin")
    roles = client.get("/lookups", headers=ah).json()["roles"]
    assert set(roles) == {"STUDENT", "FACULTY", "LIBRARY_STAFF", "ADMIN", "EXTERNAL_USER"}
    for role in ("PANELIST", "DEAN", "ADVISER", "HEAD_LIBRARIAN"):
        body = {"username": "x" + role.lower(), "password": "Drass2026", "role": role, "full_name": "X", "email": "x@x.xx"}
        assert client.post("/users", headers=ah, json=body).status_code == 422


# ---------------- search / recommendations ----------------
def _lower_threshold(client, value="0.1"):
    r = client.put("/admin/settings", headers=login(client, "admin"), json={"values": {"semantic_threshold": value}})
    assert r.status_code == 200


def test_tc06_semantic_ranking_pipeline(demo):
    _lower_threshold(demo)
    h = login(demo, "student2")
    r = demo.post("/search/semantic", headers=h, json={"query": "research projects that use technology to improve student learning"}).json()
    assert r["count"] >= 1 and r["results"][0]["title"].startswith("Gamified")
    scores = [x["score"] for x in r["results"]]
    assert scores == sorted(scores, reverse=True)
    titles = " ".join(x["title"] for x in r["results"])
    assert "Irrigation" not in titles and "Flood" not in titles
    assert r["results"][0]["score_label"].startswith("Semantic relevance:")


def test_tc07_threshold_no_weak_results(demo):
    h = login(demo, "external1")
    r = demo.post("/search/semantic", headers=h, json={"query": "volcanic eruption lava geology"}).json()
    assert r["count"] == 0 and r["message"] == "No sufficiently related research was found."
    assert r["hint"] == "Try removing filters or browsing the repository."


def test_search_filters_narrow_results(demo):
    _lower_threshold(demo)
    h = login(demo, "student2")
    cats = {c["name"]: c["id"] for c in lookups(demo, h)["categories"]}
    r = demo.post("/search/semantic", headers=h, json={"query": "technology to improve student learning",
                                                       "filters": {"category_id": cats["Health"]}}).json()
    assert all(x["category"] == "Health" for x in r["results"])


def test_repository_filters_and_pagination(demo):
    h = login(demo, "external1")
    r = demo.get("/repository?page_size=5&sort=year&order=asc", headers=h).json()
    assert r["total"] == 12 and len(r["items"]) == 5
    assert demo.get("/repository?year=2026", headers=h).json()["total"] == 2
    assert demo.get("/repository?keyword=dengue", headers=h).json()["total"] == 1
    assert demo.get("/repository?author=Hannah", headers=h).json()["total"] == 1
    assert demo.get("/repository?page_size=1000", headers=h).status_code == 422
    assert demo.get("/repository?sort=password_hash", headers=h).status_code == 422


def test_recommendations_exclude_self_and_cap(demo):
    _lower_threshold(demo)
    h = login(demo, "student2")
    wid = next(i["work_id"] for i in demo.get("/repository", headers=h).json()["items"] if i["title"].startswith("Gamified"))
    r = demo.get(f"/recommendations/{wid}", headers=h).json()
    assert len(r["items"]) <= 5 and all(i["work_id"] != wid for i in r["items"])


def test_tc12_embedding_failure_keeps_archive_and_retry(client, monkeypatch):
    def boom():
        raise RuntimeError("model unavailable")
    monkeypatch.setattr(index_service, "get_embedder", boom)
    sh = login(client, "student1")
    wid = ready_submission(client, sh)
    client.post(f"/submissions/{wid}/submit", headers=sh)
    archive_chain(client, wid)
    assert client.get(f"/submissions/{wid}", headers=sh).json()["status"] == "ARCHIVED"
    admin = login(client, "admin")
    s = client.get("/admin/indexing", headers=admin).json()
    assert s["failed"] == 1 and s["failures"][0]["work_id"] == wid
    assert any(n["type"] == "INDEXING" for n in client.get("/notifications", headers=admin).json()["items"])
    monkeypatch.undo()
    assert client.post("/admin/indexing/rebuild", headers=admin, json={"mode": "failed"}).status_code == 200
    s = client.get("/admin/indexing", headers=admin).json()
    assert s["failed"] == 0 and s["indexed"] == 1


def test_metadata_edit_marks_and_reindexes(demo):
    lh = login(demo, "headlibrarian")
    wid = demo.get("/repository", headers=lh).json()["items"][0]["work_id"]
    r = demo.patch(f"/repository/{wid}", headers=lh, json={"title": "Edited Title For Reindex"})
    assert r.status_code == 200
    with SessionLocal() as db:
        assert db.query(Embedding).filter_by(work_id=wid).one().status == "COMPLETE"
    assert demo.patch(f"/repository/{wid}", headers=login(demo, "external1"), json={"title": "x"}).status_code == 403


# ---------------- reader ----------------
def test_tc08_reader_pages_and_no_download(demo):
    pytest.importorskip("fitz")
    h = login(demo, "external1")
    wid = demo.get("/repository", headers=h).json()["items"][0]["work_id"]
    info = demo.get(f"/reader/{wid}/info", headers=h).json()
    assert info["page_count"] == 3
    r = demo.get(f"/reader/{wid}/pages/1?scale=1.2", headers=h)
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG" and "no-store" in r.headers["cache-control"]
    assert demo.get(f"/reader/{wid}/pages/99", headers=h).status_code == 404
    assert demo.get(f"/reader/{wid}/pages/1?scale=50", headers=h).status_code == 422
    assert demo.get(f"/reader/{wid}/download", headers=h).status_code == 404
    logs = demo.get("/activity-logs", headers=login(demo, "admin")).json()["items"]
    assert any(l["event_type"] == "PDF_PAGE_VIEWED" and l["user"] == "external1" for l in logs)


def test_reader_requires_login(demo):
    assert demo.get("/reader/1/pages/1").status_code == 401


# ---------------- reports / logs / admin ----------------
def test_reports_rbac_and_content(demo):
    sh = login(demo, "student1")
    wid = ready_submission(demo, sh)
    demo.post(f"/submissions/{wid}/submit", headers=sh)
    for u in ("student1", "faculty1", "headlibrarian", "libstaff1", "external1"):          # reports are Administrator-only (FR16)
        assert demo.get("/reports/submissions", headers=login(demo, u)).status_code == 403, u
    admin = login(demo, "admin")
    assert demo.get("/reports/pending-verification", headers=admin).json()["count"] == 1
    assert demo.get("/reports/archived", headers=admin).json()["count"] == 12
    assert demo.get("/reports/user-activity", headers=admin).json()["count"] > 0
    assert demo.get("/reports/system-activity", headers=admin).status_code == 200
    csv = demo.get("/reports/archived?format=csv", headers=admin)
    assert csv.headers["content-type"].startswith("text/csv") and csv.text.startswith("Reference,")
    assert demo.get("/reports/archived?date_from=garbage", headers=admin).status_code == 422
    assert demo.get("/reports/bogus", headers=admin).status_code == 422


def test_tc11_audit_records_complete(client):
    sh = login(client, "student1")
    wid = ready_submission(client, sh)
    client.post(f"/submissions/{wid}/submit", headers=sh)
    archive_chain(client, wid)
    rows = audit_actions(client)
    actions = {r["action"] for r in rows}
    assert {"LOGIN_SUCCESS", "SUBMISSION_CREATED", "FILE_UPLOADED", "SUBMISSION_SUBMITTED", "RESEARCH_ARCHIVED"} <= actions
    assert all(r["timestamp"] and r["action"] and r["result"] for r in rows)
    assert client.delete("/audit-logs/1", headers=login(client, "admin")).status_code in (404, 405)


def test_admin_user_management_and_settings(client):
    a = login(client, "admin")
    bad = client.post("/users", headers=a, json={"username": "newuser", "password": "short", "role": "STUDENT",
                                                  "full_name": "N U", "email": "n@x.io"})
    assert bad.status_code == 422
    ok = client.post("/users", headers=a, json={"username": "newuser", "password": "longenough1", "role": "STUDENT",
                                                 "full_name": "N U", "email": "n@x.io"})
    assert ok.status_code == 200
    assert client.post("/users", headers=a, json={"username": "newuser", "password": "longenough1", "role": "STUDENT",
                                                   "full_name": "N U", "email": "n2@x.io"}).status_code == 409
    uid = ok.json()["user_id"]
    assert client.patch(f"/users/{uid}", headers=a, json={"role": "FACULTY"}).json()["role"] == "FACULTY"
    assert client.put("/admin/settings", headers=a, json={"values": {"semantic_threshold": "7"}}).status_code == 422
    assert client.put("/admin/settings", headers=a, json={"values": {"semantic_threshold": "0.4"}}).status_code == 200
    acts = [r["action"] for r in client.get("/audit-logs?page_size=200", headers=a).json()["items"]]
    assert {"USER_CREATED", "ROLE_CHANGED", "SETTING_CHANGED"} <= set(acts)
    own = next(u for u in client.get("/users", headers=a).json()["items"] if u["username"] == "admin")
    assert client.post(f"/users/{own['user_id']}/deactivate", headers=a).status_code == 422


def test_dashboards_per_role(demo):
    assert "pending_verification" in demo.get("/dashboard", headers=login(demo, "headlibrarian")).json()
    assert "verified_total" in demo.get("/dashboard", headers=login(demo, "headlibrarian")).json()
    assert "verified_total" not in demo.get("/dashboard", headers=login(demo, "libstaff1")).json()
    assert "total_works" in demo.get("/dashboard", headers=login(demo, "admin")).json()
    assert "submissions" in demo.get("/dashboard", headers=login(demo, "student1")).json()
    assert demo.get("/dashboard", headers=login(demo, "external1")).json()["archived"] == 12


def test_error_format_for_unknown_route(client):
    r = client.get("/nope")
    assert r.status_code == 404 and r.json()["success"] is False and "error_code" in r.json()
