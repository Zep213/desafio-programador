import os

import pytest

from app.errors import LayoutDesconhecidoError
from app.services.extractors.holerite import HoleriteExtractor

EXEMPLOS = os.path.join(os.path.dirname(__file__), "..", "..", "exemplos")


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
