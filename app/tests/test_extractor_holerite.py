import os

import pytest

from app.errors import LayoutDesconhecidoError
from app.services.extractors.holerite import (
    HoleriteExtractor,
    _dividir_por_competencia,
    _extrair_fields_e_bases,
    _localizar_cabecalho,
)
from app.services.reader import Palavra

EXEMPLOS = os.path.join(os.path.dirname(__file__), "..", "..", "exemplos")


def _p(texto: str, x0: float, top: float = 0.0) -> Palavra:
    return Palavra(texto=texto, x0=x0, x1=x0 + len(texto) * 6, top=top, bottom=top + 10, confianca=95.0)


@pytest.fixture(scope="module")
def payroll_03():
    return HoleriteExtractor().extract(os.path.join(EXEMPLOS, "payroll-03.pdf"))


@pytest.fixture(scope="module")
def payroll_02():
    return HoleriteExtractor().extract(os.path.join(EXEMPLOS, "payroll-02.pdf"))


def test_payroll_03_competencia_por_pagina(payroll_03):
    assert len(payroll_03["pages"]) == 5
    competencias = [(p["year"], p["month"]) for p in payroll_03["pages"]]
    assert competencias == [
        ("2019", "10"),
        ("2019", "11"),
        ("2019", "12"),
        ("2020", "01"),
        ("2020", "02"),
    ]


def test_payroll_03_field_com_codigo_referencia_e_valor(payroll_03):
    p1 = payroll_03["pages"][0]
    campo = next(f for f in p1["fields"] if f["code"] == "0105")
    assert campo == {"code": "0105", "label": "Dias Trabalhados", "reference": "30,00", "value": "1.678,61"}


def test_payroll_03_label_nao_perde_palavra_que_transborda_coluna(payroll_03):
    p1 = payroll_03["pages"][0]
    campo = next(f for f in p1["fields"] if f["code"] == "2027")
    assert campo["label"] == "Horas Extras 100% Noturna"
    assert campo["reference"] == "2,92"


def test_payroll_03_bases_nunca_em_fields(payroll_03):
    p1 = payroll_03["pages"][0]
    labels_fields = {f["label"] for f in p1["fields"]}
    assert "Total" not in labels_fields
    assert "Líqüido" not in labels_fields
    assert not any("Base" in label for label in labels_fields)


def test_payroll_03_base_com_dois_valores_na_mesma_linha_nao_perde_nenhum(payroll_03):
    p1 = payroll_03["pages"][0]
    valores_total = [b["value"] for b in p1["bases"] if b["label"] == "Total"]
    assert valores_total == ["1.967,07", "859,46"]


def test_payroll_03_bases_inline_com_dois_pontos(payroll_03):
    p1 = payroll_03["pages"][0]
    labels = {b["label"] for b in p1["bases"]}
    assert "Base I.N.S.S." in labels
    assert "F.G.T.S. do Mês" in labels


def test_payroll_02_multiplas_competencias_na_mesma_pagina(payroll_02):
    paginas_fisicas = {p["page"] for p in payroll_02["pages"]}
    assert len(payroll_02["pages"]) > len(paginas_fisicas)


def test_payroll_02_codigo_curto_nao_engole_inicio_do_label(payroll_02):
    bloco1 = payroll_02["pages"][0]
    campo = next(f for f in bloco1["fields"] if f["code"] == "010")
    assert campo["label"] == "VENCIMENTO PADRAO-VP"


def test_payroll_02_valor_negativo_mantido_como_impresso(payroll_02):
    bloco1 = payroll_02["pages"][0]
    campo = next(f for f in bloco1["fields"] if f["code"] == "803")
    assert campo["value"] == "-433,20"
    assert campo["reference"] == "6.188,63"


def test_payroll_01_layout_nao_reconhecido_levanta_erro_honesto():
    with pytest.raises(LayoutDesconhecidoError):
        HoleriteExtractor().extract(os.path.join(EXEMPLOS, "payroll-01.pdf"))


def test_localizar_cabecalho_ignora_linha_de_titulo_de_secao():
    linha_titulo = [_p("Proventos", 142.8, top=193.4), _p("Descontos", 371.5, top=193.4)]
    linha_cabecalho_real = [
        _p("Descrição", 44.4, top=199.4),
        _p("Qtde", 182.2, top=200.4),
        _p("Valor", 243.8, top=199.4),
        _p("Descrição", 273.1, top=199.4),
        _p("Qtde", 410.6, top=199.4),
        _p("Valor", 469.0, top=200.4),
    ]

    achado = _localizar_cabecalho([linha_titulo, linha_cabecalho_real])

    assert achado is not None
    assert achado["top"] == 199.4


def test_linha_de_valores_sem_rotulo_textual_e_descartada_nao_inventa_label():
    colunas = [
        {"papel": "nome", "centro": 44},
        {"papel": "referencia", "centro": 150},
        {"papel": "valor", "centro": 250},
    ]
    linha = [_p("1.300,00", 44), _p("2.227,04", 150), _p("0,00", 250)]

    fields, bases = _extrair_fields_e_bases([linha], colunas)

    assert fields == []
    assert bases == []


def test_dividir_por_competencia_aceita_marcador_solto_sem_rotulo():
    linha_marcador = [_p("SETEMBRO/2019", 273.1, top=91.9)]
    linha_dado = [_p("SALARIO", 44.4, top=210.2), _p("953,36", 229.9, top=210.2)]

    blocos = _dividir_por_competencia([linha_marcador, linha_dado])

    assert len(blocos) == 1
    competencia, linhas_bloco = blocos[0]
    assert competencia == ("2019", "09")
    assert linhas_bloco == [linha_dado]


def test_duas_verbas_lado_a_lado_na_mesma_linha_cada_uma_com_seu_rotulo():
    colunas = [
        {"papel": "nome", "centro": 44},
        {"papel": "referencia", "centro": 182},
        {"papel": "valor", "centro": 243},
        {"papel": "nome", "centro": 273},
        {"papel": "referencia", "centro": 410},
        {"papel": "valor", "centro": 469},
    ]
    linha = [
        _p("SALARIO", 44),
        _p("953,36", 230),
        _p("INSS", 273),
        _p("MES", 296),
        _p("200,43", 455),
    ]

    fields, bases = _extrair_fields_e_bases([linha], colunas)

    assert fields == [
        {"code": "", "label": "SALARIO", "reference": "", "value": "953,36"},
        {"code": "", "label": "INSS MES", "reference": "", "value": "200,43"},
    ]
    assert bases == []


def test_rotulo_compartilhado_por_duas_colunas_de_valor_reaproveita_o_ultimo():
    colunas = [
        {"papel": "nome", "centro": 44},
        {"papel": "valor", "centro": 200},
        {"papel": "valor", "centro": 300},
    ]
    linha = [_p("Total", 44), _p("1.967,07", 190), _p("859,46", 290)]

    fields, bases = _extrair_fields_e_bases([linha], colunas)

    assert fields == []
    assert bases == [
        {"label": "Total", "value": "1.967,07"},
        {"label": "Total", "value": "859,46"},
    ]


def test_dividir_por_competencia_com_rotulo_nao_usa_fallback_solto():
    linha_rotulo = [_p("Mês/Ano:", 44.0, top=50.0), _p("08/2018", 100.0, top=50.0)]
    linha_dado = [_p("X", 44.4, top=60.0)]

    blocos = _dividir_por_competencia([linha_rotulo, linha_dado])

    assert len(blocos) == 1
    assert blocos[0][0] == ("2018", "08")
