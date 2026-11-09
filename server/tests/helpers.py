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
            "department_id": lk["programs"][0]["department_id"],
            "adviser_id": lk["faculty"][0]["id"], "dean_id": lk["faculty"][-1]["id"], "keywords": list(keywords)}
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


CHECKLIST = dict(adviser_signed=True, panelists_signed=True, dean_signed=True, researchers_signed=True, sheet_complete=True)


def verify(client, h, work_id, decision="APPROVE", remarks="", publication_status="PUBLIC", expected_version=None, **checklist):
    """Head Librarian's signatory verification. The checklist defaults to everything confirmed."""
    body = {"decision": decision, **{**CHECKLIST, **checklist}, "remarks": remarks, "expected_version": expected_version}
    if decision == "APPROVE":
        body["publication_status"] = publication_status
    return client.post(f"/verifications/{work_id}", headers=h, json=body)


def archive_chain(client, work_id, publication_status="PUBLIC"):
    """The Head Librarian verifies the signatories and gives the final approval: Pending Verification -> Archived."""
    r = verify(client, login(client, "headlibrarian"), work_id, "APPROVE", publication_status=publication_status)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ARCHIVED", r.json()
