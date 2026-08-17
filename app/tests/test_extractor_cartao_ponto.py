import os

import pytest

from app.errors import LayoutDesconhecidoError
from app.services import reader
from app.services.extractors.cartao_ponto import (
    CartaoPontoExtractor,
    _extrair_dias_fallback,
    _extrair_dias_por_coluna,
)
from app.services.reader import PaginaLida, Palavra

EXEMPLOS = os.path.join(os.path.dirname(__file__), "..", "..", "exemplos")
CAMINHO_EXEMPLO = os.path.join(EXEMPLOS, "time-card-01.pdf")


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


def test_faixa_colada_pelo_ocr_vira_dois_punches():
    colunas = [
        {"papel": "dia", "centro": 10.0},
        {"papel": "entrada", "centro": 60.0},
        {"papel": "saida", "centro": 110.0},
    ]
    linhas = [
        [_palavra("5", 5, 0), _palavra("08:48-16:11", 55, 0)],
    ]

    dias = _extrair_dias_por_coluna(linhas, colunas)

    punches = dias[0]["punches"]
    assert [(p["kind"], p["time_hhmm"]) for p in punches] == [
        ("IN", "08:48"),
        ("OUT", "16:11"),
    ]
    assert punches[0]["time_raw"] == "08:48-16:11"
    assert punches[1]["time_raw"] == "08:48-16:11"


def test_fallback_descarta_horarios_isolados_a_direita_como_totais():
    # Documento sem cabeçalho reconhecido (ex.: coluna "Data" em vez de "Dia",
    # ou cabeçalho ilegível por OCR) — 4 batidas reais bem próximas, depois um
    # salto grande antes de valores tipo H.Ext/Atraso/Ad.Not que também parecem
    # horário mas não são batida nenhuma.
    linha = [
        _palavra("16/12/2019", 5, 0),
        _palavra("07:00", 100, 0),
        _palavra("12:00", 140, 0),
        _palavra("13:00", 180, 0),
        _palavra("17:00", 220, 0),
        _palavra("01:15", 400, 0),  # H.Ext
        _palavra("00:30", 450, 0),  # Atraso
    ]

    dias = _extrair_dias_fallback([linha])

    assert len(dias) == 1
    assert [p["time_hhmm"] for p in dias[0]["punches"]] == ["07:00", "12:00", "13:00", "17:00"]


def test_fallback_nao_corta_quando_espacamento_e_uniforme():
    # Sem salto dominante (espaçamento regular do início ao fim), não há
    # sinal geométrico de "área de totais" — melhor manter tudo a arriscar
    # cortar batida real por engano.
    linha = [
        _palavra("16/12/2019", 5, 0),
        _palavra("07:00", 100, 0),
        _palavra("12:00", 150, 0),
        _palavra("13:00", 200, 0),
        _palavra("17:00", 250, 0),
    ]

    dias = _extrair_dias_fallback([linha])

    assert [p["time_hhmm"] for p in dias[0]["punches"]] == ["07:00", "12:00", "13:00", "17:00"]


def test_palavra_com_confianca_ocr_baixa_vira_incerta():
    colunas = [
        {"papel": "dia", "centro": 10.0},
        {"papel": "entrada", "centro": 60.0},
        {"papel": "saida", "centro": 110.0},
    ]
    palavra_incerta = Palavra(texto="08:48", x0=55, x1=75, top=0, bottom=10, confianca=40.0)
    linhas = [[_palavra("5", 5, 0), palavra_incerta]]

    dias = _extrair_dias_por_coluna(linhas, colunas)

    punch = dias[0]["punches"][0]
    assert punch["time_raw"] == "08:48"
    assert punch["time_hhmm"] == "??:??"


def test_dias_reconhecidos_sem_nenhuma_batida_levanta_erro_honesto(monkeypatch):
    # Reproduz o formato do time-card-04.pdf no caminho de fallback: fragmentos
    # de cabeçalho de quinzena ("1.QUINZENA", números soltos) viram "dias" por
    # começarem com 1-2 dígitos, mas nenhum tem horário por perto. Zero batidas
    # no documento inteiro não é uma leitura escassa — é layout não identificado.
    palavras = [_palavra("1.QUINZENA", 5, 0), _palavra("6", 5, 10), _palavra("4", 5, 20)]
    pagina = PaginaLida(page=1, rota="digital", palavras=palavras)
    monkeypatch.setattr(reader, "ler", lambda caminho: [pagina])

    with pytest.raises(LayoutDesconhecidoError):
        CartaoPontoExtractor().extract("qualquer.pdf")


def test_time_card_04_layout_nao_reconhecido_levanta_erro_honesto():
    with pytest.raises(LayoutDesconhecidoError):
        CartaoPontoExtractor().extract(os.path.join(EXEMPLOS, "time-card-04.pdf"))


@pytest.mark.parametrize("nome", ["time-card-01.pdf", "time-card-02.pdf", "time-card-03.pdf"])
def test_documentos_reais_com_batida_nao_regridem(nome):
    transcricao = CartaoPontoExtractor().extract(os.path.join(EXEMPLOS, nome))
    total_batidas = sum(len(d["punches"]) for p in transcricao["pages"] for d in p["days"])
    assert total_batidas > 0
