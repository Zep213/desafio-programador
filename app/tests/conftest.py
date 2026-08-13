import os
import tempfile

_TMPDIR = tempfile.mkdtemp(prefix="quickfiller-test-")
os.environ["DB_PATH"] = os.path.join(_TMPDIR, "app.db")
os.environ["UPLOAD_DIR"] = os.path.join(_TMPDIR, "uploads")
os.environ["MAX_UPLOAD_MB"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.models.repository import inicializar_schema  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    inicializar_schema()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def pdf_valido() -> bytes:
    return b"%PDF-1.4\n%conteudo fake de pdf para teste\n%%EOF"
