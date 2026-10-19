import os
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="drass_test_")
os.environ.update(DATABASE_URL=f"sqlite:///{_TMP}/test.db", FILE_STORAGE_ROOT=f"{_TMP}/storage",
                  EMBEDDER="hash", BCRYPT_ROUNDS="4", ENABLE_DOCS="true")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from server.app.db import Base, SessionLocal, engine  # noqa: E402
from server.app.main import app  # noqa: E402
from server.app.core import ratelimit  # noqa: E402
from server.app.seed import seed_core, seed_demo, seed_roster  # noqa: E402
from server.app.services import files_service, embedder  # noqa: E402

STORAGE = os.environ["FILE_STORAGE_ROOT"]


@pytest.fixture()
def client():
    """Fresh database + storage per test, seeded with roles/lookups/demo users."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    shutil.rmtree(STORAGE, ignore_errors=True)
    files_service.ensure_dirs()
    embedder.set_embedder(None)
    ratelimit.reset()
    with SessionLocal() as db:
        seed_core(db)
        seed_roster(db)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def demo(client):
    with SessionLocal() as db:
        seed_demo(db)
    return client
