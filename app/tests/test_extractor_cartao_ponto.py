import os

import pytest

from app.services.extractors.cartao_ponto import CartaoPontoExtractor, _extrair_dias_por_coluna
from app.services.reader import Palavra

CAMINHO_EXEMPLO = os.path.join(
    os.path.dirname(__file__), "..", "..", "exemplos", "time-card-01.pdf"
)


@pytest.fixture(scope="module")
def transcricao():
    return CartaoPontoExtractor().extract(CAMINHO_EXEMPLO)


def test_todas_as_paginas_tem_dias(transcricao):
    assert len(transcricao["pages"]) == 5
    for pagina in transcricao["pages"]:
        assert len(pagina["days"]) > 0


def test_dia_sem_batida_fica_com_punches_vazio(transcricao):
    dia1 = transcricao["pages"][0]["days"][0]
    assert dia1["date_raw"] == "1 - DOM"
    assert dia1["punches"] == []


def test_turno_e_continuacao_viram_quatro_batidas_alternadas(transcricao):
    dia2 = next(d for d in transcricao["pages"][0]["days"] if d["date_raw"] == "2 - SEG")
    horarios = [(p["kind"], p["time_hhmm"]) for p in dia2["punches"]]
    assert horarios == [
        ("IN", "09:03"),
        ("OUT", "14:05"),
        ("IN", "15:12"),
        ("OUT", "18:36"),
    ]


def test_marcador_de_dia_repetido_nao_faz_merge(transcricao):
    dias_17 = [d for d in transcricao["pages"][0]["days"] if d["date_raw"] == "17 - TER"]
    assert len(dias_17) == 2
    assert [p["time_hhmm"] for p in dias_17[0]["punches"]] == ["09:09", "13:01"]
    assert [p["time_hhmm"] for p in dias_17[1]["punches"]] == ["14:16", "18:50"]


def test_nenhum_horario_suspeito_no_documento_limpo(transcricao):
    for pagina in transcricao["pages"]:
        for dia in pagina["days"]:
            for punch in dia["punches"]:
                assert "?" not in punch["time_hhmm"], (dia["date_raw"], punch)


def test_ordem_segue_o_documento_nao_ordena(transcricao):
    dias_pagina1 = [d["date_raw"] for d in transcricao["pages"][0]["days"]]
    numeros = [int(d.split(" - ")[0]) for d in dias_pagina1]
    assert numeros == sorted(numeros)


def _palavra(texto, x0, top):
    return Palavra(texto=texto, x0=x0, x1=x0 + 20, top=top, bottom=top + 10, confianca=100.0)


def test_ordem_fora_de_sequencia_nao_e_reordenada():
    colunas = [
        {"papel": "dia", "centro": 10.0},
        {"papel": "entrada", "centro": 60.0},
        {"papel": "saida", "centro": 110.0},
    ]
    linhas = [
        [_palavra("5", 5, 0), _palavra("08:00", 55, 0)],
        [_palavra("3", 5, 10), _palavra("09:00", 55, 10)],
        [_palavra("5", 5, 20), _palavra("10:00", 55, 20)],
    ]

    dias = _extrair_dias_por_coluna(linhas, colunas)

    assert [d["date_raw"] for d in dias] == ["5", "3", "5"]
    assert dias[0]["punches"][0]["time_hhmm"] == "08:00"
    assert dias[1]["punches"][0]["time_hhmm"] == "09:00"
    assert dias[2]["punches"][0]["time_hhmm"] == "10:00"
