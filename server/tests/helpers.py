from server.app.seed import DEMO_PASSWORD, make_pdf

PDF = make_pdf("Test manuscript", "Body text for testing.", pages=2)
ZIP = b"PK\x03\x04" + b"\x00" * 200


def login(client, username, password=DEMO_PASSWORD):
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def lookups(client, h):
    return client.get("/lookups", headers=h).json()


def new_draft(client, h, title="Smart Attendance Monitoring for Rural Schools", abstract="An attendance system using QR codes.",
              authors=None, year=2026, keywords=("attendance", "qr code")):
    lk = lookups(client, h)
    body = {"title": title, "abstract": abstract, "year": year, "program_id": lk["programs"][0]["id"],
            "department_id": lk["programs"][0]["department_id"], "category_id": lk["categories"][0]["id"],
            "adviser_id": lk["advisers"][0]["id"], "keywords": list(keywords)}
    if authors:
        body["authors"] = [{"name": a} for a in authors]
    r = client.post("/submissions", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["work_id"]


def upload(client, h, work_id, kind="MANUSCRIPT", filename="manuscript.pdf", data=PDF):
    return client.put(f"/submissions/{work_id}/files/{kind}", headers=h, params={"filename": filename}, content=data)


def ready_submission(client, h, **kw):
    wid = new_draft(client, h, **kw)
    assert upload(client, h, wid).status_code == 200
    return wid


def decide(client, h, work_id, decision, comments="", expected_version=None):
    """decision: approve|return|reject. Uses the caller's review queue to find the assignment."""
    q = client.get("/reviews/queue", headers=h).json()["items"]
    item = next(i for i in q if i["work_id"] == work_id)
    return client.post(f"/reviews/{item['assignment_id']}/{decision}", headers=h,
                       json={"comments": comments, "expected_version": expected_version})


def archive_chain(client, work_id):
    steps = [("adviser1", "UNDER_PANEL_REVIEW"), ("panelist1", "UNDER_PANEL_REVIEW"), ("panelist2", "UNDER_DEAN_REVIEW"),
             ("dean", "UNDER_HEAD_LIBRARIAN_REVIEW"), ("headlibrarian", "ARCHIVED")]
    for user, expected in steps:
        r = decide(client, login(client, user), work_id, "approve")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == expected, r.json()
