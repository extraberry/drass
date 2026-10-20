"""Admin override approval + 'panel approved offline' shortcut (API level)."""
from server.app.db import SessionLocal
from server.app.models import ResearchWork
from server.tests.helpers import *   # noqa: F401,F403


def _submitted(client, **kw):
    sh = login(client, "student1")
    wid = ready_submission(client, sh, **kw)
    assert client.post(f"/submissions/{wid}/submit", headers=sh).status_code == 200
    return sh, wid


def _actions(client):
    return {i["action"] for i in client.get("/audit-logs?page_size=200", headers=login(client, "admin")).json()["items"]}


def _queue_ids(client, user):
    return [i["work_id"] for i in client.get("/reviews/queue", headers=login(client, user)).json()["items"]]


def _approve_offline(client, wid, ref="Panel letter 2026-10-12 Ref 041", comments=""):
    ah = login(client, "adviser1")
    q = client.get("/reviews/queue", headers=ah).json()["items"]
    aid = next(i["assignment_id"] for i in q if i["work_id"] == wid)
    return client.post(f"/reviews/{aid}/approve", headers=ah,
                       json={"comments": comments, "panel_offline": True, "panel_offline_reference": ref})


# ---------------- panel approved offline ----------------
def test_offline_panel_goes_straight_to_head_librarian_and_archives(client):
    sh, wid = _submitted(client)
    r = _approve_offline(client, wid)
    assert r.status_code == 200 and r.json()["status"] == "UNDER_HEAD_LIBRARIAN_REVIEW"
    assert wid not in _queue_ids(client, "panelist1") and wid not in _queue_ids(client, "dean")
    assert wid in _queue_ids(client, "headlibrarian")
    d = client.get(f"/submissions/{wid}", headers=sh).json()
    assert d["review_history"][0]["stage"] == "ADVISER" and "PANEL APPROVED OFFLINE" in d["review_history"][0]["comments"]
    assert "Ref 041" in d["review_history"][0]["comments"]
    assert decide(client, login(client, "headlibrarian"), wid, "approve").json()["status"] == "ARCHIVED"
    acts = _actions(client)
    assert "REVIEW_PANEL_OFFLINE_APPROVED" in acts and "RESEARCH_ARCHIVED" in acts


def test_offline_panel_requires_reference(client):
    _, wid = _submitted(client)
    assert _approve_offline(client, wid, ref="  ").status_code == 422
    assert _approve_offline(client, wid, ref="ab").status_code == 422
    with SessionLocal() as db:
        assert db.get(ResearchWork, wid).current_status == "UNDER_ADVISER_REVIEW"     # nothing changed


def test_offline_panel_setting_can_route_to_dean(client):
    ah = login(client, "admin")
    assert client.put("/admin/settings", headers=ah, json={"values": {"offline_panel_skips_dean": "false"}}).status_code == 200
    _, wid = _submitted(client)
    assert _approve_offline(client, wid).json()["status"] == "UNDER_DEAN_REVIEW"
    assert wid in _queue_ids(client, "dean")


def test_offline_panel_not_allowed_on_return_or_other_stage(client):
    _, wid = _submitted(client)
    ah = login(client, "adviser1")
    aid = client.get("/reviews/queue", headers=ah).json()["items"][0]["assignment_id"]
    r = client.post(f"/reviews/{aid}/return", headers=ah, json={"comments": "fix", "panel_offline": True, "panel_offline_reference": "letter 1"})
    assert r.status_code == 422
    assert decide(client, ah, wid, "approve").json()["status"] == "UNDER_PANEL_REVIEW"        # normal path still works
    pq = client.get("/reviews/queue", headers=login(client, "panelist1")).json()["items"][0]["assignment_id"]
    r = client.post(f"/reviews/{pq}/approve", headers=login(client, "panelist1"),
                    json={"comments": "", "panel_offline": True, "panel_offline_reference": "letter 1"})
    assert r.status_code == 422


# ---------------- admin override ----------------
def _override(client, wid, mode="next", reason="Signed approval letters on file", user="admin", version=None):
    return client.post(f"/admin/works/{wid}/override-approve", headers=login(client, user),
                       json={"mode": mode, "reason": reason, "expected_version": version})


def test_admin_override_next_stage_cancels_pending_adviser(client):
    _, wid = _submitted(client)
    r = _override(client, wid, "next")
    assert r.status_code == 200 and r.json()["status"] == "UNDER_PANEL_REVIEW"
    assert wid not in _queue_ids(client, "adviser1")                    # adviser review no longer pending
    assert wid in _queue_ids(client, "panelist1")                       # next stage created normally
    hist = client.get(f"/submissions/{wid}", headers=login(client, "student1")).json()["review_history"]
    assert any("ADMIN OVERRIDE" in h["comments"] for h in hist)
    assert "REVIEW_ADMIN_OVERRIDE" in _actions(client)


def test_admin_override_archive_now_indexes(client):
    _, wid = _submitted(client)
    r = _override(client, wid, "archive")
    assert r.status_code == 200 and r.json()["status"] == "ARCHIVED"
    with SessionLocal() as db:
        w = db.get(ResearchWork, wid)
        assert w.archived_at is not None and w.current_status == "ARCHIVED"
    assert wid not in _queue_ids(client, "adviser1")


def test_admin_override_requires_reason_and_admin(client):
    _, wid = _submitted(client)
    assert _override(client, wid, reason="no").status_code == 422
    assert _override(client, wid, reason="   ").status_code == 422
    assert _override(client, wid, user="student1").status_code == 403
    assert _override(client, wid, user="adviser1").status_code == 403
    assert _override(client, wid, user="headlibrarian").status_code == 403
    with SessionLocal() as db:
        assert db.get(ResearchWork, wid).current_status == "UNDER_ADVISER_REVIEW"


def test_admin_override_rejects_non_review_statuses_and_stale_version(client):
    sh = login(client, "student1")
    draft = ready_submission(client, sh)
    assert _override(client, draft, "archive").status_code == 409        # DRAFT is not under review
    _, wid = _submitted(client, title="Another Unique Study on Library Queue Management")
    assert _override(client, wid, "next", version=999).status_code == 409
    assert _override(client, wid, "archive").json()["status"] == "ARCHIVED"
    assert _override(client, wid, "archive").status_code == 409          # already archived
    assert _override(client, wid, "bogus").status_code in (409, 422)
