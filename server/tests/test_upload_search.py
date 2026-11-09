"""Upload-limit text and hybrid (meaning + words) search."""
import os
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from server.app import db as dbmod
from server.app.db import Base, SessionLocal
from server.app.models import ResearchWork, StudentRoster, User
from server.app.seed import seed_core, seed_roster
from server.tests.conftest import STORAGE
from server.tests.helpers import *   # noqa: F401,F403
from server.tests.helpers import DEMO_PASSWORD


# ---------------- upload limits are stated clearly ----------------
def test_upload_limits_are_published_for_every_kind_of_file(client):
    r = client.get("/public/upload-limits")                     # no login needed: the form shows it before any upload
    assert r.status_code == 200
    rows = {x["file_type"]: x for x in r.json()["limits"]}
    assert rows["MANUSCRIPT"]["max_mb"] == 100 and rows["VIDEO"]["max_mb"] == 500 and rows["SOURCE_CODE"]["max_mb"] == 500
    assert ".pdf" in rows["MANUSCRIPT"]["extensions"] and ".mp4" in rows["VIDEO"]["extensions"] and ".zip" in rows["SOURCE_CODE"]["extensions"]


def test_admin_changes_show_up_in_the_published_limits(client):
    admin = login(client, "admin")
    assert client.put("/admin/settings", headers=admin, json={"values": {"max_video_mb": "250", "max_source_code_mb": "300"}}).status_code == 200
    rows = {x["file_type"]: x for x in client.get("/public/upload-limits").json()["limits"]}
    assert rows["VIDEO"]["max_mb"] == 250 and rows["SOURCE_CODE"]["max_mb"] == 300


def test_each_kind_of_file_uses_its_own_limit_and_message_names_it(client):
    admin = login(client, "admin")
    client.put("/admin/settings", headers=admin, json={"values": {"max_video_mb": "1", "max_source_code_mb": "1"}})
    h = login(client, "student1")
    wid = new_draft(client, h)
    big_zip = b"PK\x03\x04" + b"\x00" * (1024 * 1024 + 10)
    r = upload(client, h, wid, "SOURCE_CODE", "code.zip", big_zip)
    assert r.status_code == 422 and "1 MB" in r.json()["message"] and "source code" in r.json()["message"].lower()
    big_mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * (1024 * 1024 + 10)
    r = upload(client, h, wid, "VIDEO", "demo.mp4", big_mp4)
    assert r.status_code == 422 and "video" in r.json()["message"].lower()
    assert upload(client, h, wid, "SOURCE_CODE", "ok.zip", ZIP).status_code == 200      # small files still fine
    assert os.listdir(os.path.join(STORAGE, "temp")) == []


# ---------------- search: words, acronyms, short queries ----------------
def test_one_word_query_finds_exact_keyword_even_with_default_threshold(demo):
    h = login(demo, "student2")
    r = demo.post("/search/semantic", headers=h, json={"query": "dengue"}).json()
    assert r["count"] >= 1 and r["results"][0]["title"].startswith("Dengue")


def test_acronym_and_two_letter_queries_are_accepted(demo):
    h = login(demo, "student2")
    r = demo.post("/search/semantic", headers=h, json={"query": "LMS"})
    assert r.status_code == 200 and r.json()["results"][0]["title"].startswith("Gamified")
    r = demo.post("/search/semantic", headers=h, json={"query": "AI"})
    assert r.status_code == 200 and r.json()["results"][0]["title"].startswith("An AI Tutoring")
    assert demo.post("/search/semantic", headers=h, json={"query": "a"}).status_code == 422       # 1 character is still refused


def test_small_typo_and_plural_still_find_the_study(demo):
    h = login(demo, "student2")
    assert demo.post("/search/semantic", headers=h, json={"query": "gamifcation"}).json()["results"][0]["title"].startswith("Gamified")
    assert demo.post("/search/semantic", headers=h, json={"query": "badges and points"}).json()["count"] >= 1


def test_unrelated_query_still_returns_nothing(demo):
    h = login(demo, "student2")
    assert demo.post("/search/semantic", headers=h, json={"query": "volcanic eruption lava geology"}).json()["count"] == 0


def test_old_single_vector_embeddings_keep_working(demo):
    """Vectors saved before the multi-piece indexing hold ONE row; they must still rank."""
    import numpy as np
    from server.app.domain import search_core as sc
    from server.app.models import Embedding
    with SessionLocal() as db:
        for e in db.scalars(select(Embedding)).all():
            first = sc.matrix_from_blob(e.vector_blob, e.dimension)[0]
            e.vector_blob = sc.to_blob(first)
        db.commit()
    r = demo.post("/search/semantic", headers=login(demo, "student2"), json={"query": "dengue"}).json()
    assert r["count"] >= 1
