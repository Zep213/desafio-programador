import logging

from app.services import verificacao


def test_diverge_gera_warning_sem_pii(caplog):
    pages = [
        {
            "page": 1,
            "fields": [
                {"code": "0010", "label": "Salário Base", "reference": "", "value": "1.000,00"},
                {"code": "0998", "label": "INSS", "reference": "", "value": "-100,00"},
            ],
            "bases": [{"label": "Valor Líquido", "value": "800,00"}],
        }
    ]

    with caplog.at_level(logging.WARNING, logger="quickfiller"):
        verificacao.verificar_totais_holerite("abc123", pages)

    assert len(caplog.records) == 1
    mensagem = caplog.records[0].getMessage()
    assert "abc123" in mensagem
    assert "Salário" not in mensagem  # sem PII/dado de negócio, só números e id


def test_bate_nao_gera_warning(caplog):
    pages = [
        {
            "page": 1,
            "fields": [
                {"code": "0010", "label": "Salário Base", "reference": "", "value": "1.000,00"},
                {"code": "0998", "label": "INSS", "reference": "", "value": "-100,00"},
            ],
            "bases": [{"label": "Valor Líquido", "value": "900,00"}],
        }
    ]

    with caplog.at_level(logging.WARNING, logger="quickfiller"):
        verificacao.verificar_totais_holerite("abc123", pages)

    assert len(caplog.records) == 0


def test_valor_incerto_nao_gera_falso_positivo(caplog):
    pages = [
        {
            "page": 1,
            "fields": [{"code": "0010", "label": "Salário Base", "reference": "", "value": "?.000,00"}],
            "bases": [{"label": "Valor Líquido", "value": "900,00"}],
        }
    ]

    with caplog.at_level(logging.WARNING, logger="quickfiller"):
        verificacao.verificar_totais_holerite("abc123", pages)

    assert len(caplog.records) == 0


def test_pagina_sem_bases_liquido_nao_gera_warning(caplog):
    pages = [
        {
            "page": 1,
            "fields": [{"code": "0010", "label": "Salário Base", "reference": "", "value": "1.000,00"}],
            "bases": [{"label": "Base INSS", "value": "1.000,00"}],
        }
    ]

    with caplog.at_level(logging.WARNING, logger="quickfiller"):
        verificacao.verificar_totais_holerite("abc123", pages)

    assert len(caplog.records) == 0
