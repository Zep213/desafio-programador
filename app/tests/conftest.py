import os
import tempfile

_TMPDIR = tempfile.mkdtemp(prefix="quickfiller-test-")
os.environ["DB_PATH"] = os.path.join(_TMPDIR, "app.db")
os.environ["UPLOAD_DIR"] = os.path.join(_TMPDIR, "uploads")
os.environ["MAX_UPLOAD_MB"] = "1"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.repository import inicializar_schema


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


@pytest.fixture()
def holerite_real() -> bytes:
    caminho = os.path.join(os.path.dirname(__file__), "..", "..", "exemplos", "payroll-03.pdf")
    with open(caminho, "rb") as f:
        return f.read()
