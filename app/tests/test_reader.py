import os

import pytest

from app.errors import DocumentoGrandeDemaisError
from app.services import reader

CAMINHO_EXEMPLO = os.path.join(
    os.path.dirname(__file__), "..", "..", "exemplos", "time-card-01.pdf"
)


def test_ler_dentro_do_limite_de_paginas():
    paginas = reader.ler(CAMINHO_EXEMPLO)
    assert len(paginas) == 5


def test_ler_acima_do_limite_de_paginas_levanta_erro(monkeypatch):
    monkeypatch.setenv("MAX_PAGINAS", "3")
    with pytest.raises(DocumentoGrandeDemaisError):
        reader.ler(CAMINHO_EXEMPLO)
