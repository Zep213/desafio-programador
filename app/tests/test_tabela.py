from app.services import tabela


def test_holerite_uniao_de_colunas_com_verbas_divergentes_entre_competencias():
    value = {
        "pages": [
            {
                "page": 1,
                "year": "2020",
                "month": "01",
                "fields": [
                    {"code": "0010", "label": "Salário Base", "reference": "", "value": "1.000,00"},
                    {"code": "0020", "label": "Verba A", "reference": "", "value": "100,00"},
                ],
                "bases": [],
            },
            {
                "page": 2,
                "year": "2020",
                "month": "02",
                "fields": [
                    {"code": "0010", "label": "Salário Base", "reference": "", "value": "1.000,00"},
                ],
                "bases": [],
            },
            {
                "page": 3,
                "year": "2020",
                "month": "03",
                "fields": [
                    {"code": "0010", "label": "Salário Base", "reference": "", "value": "1.000,00"},
                    {"code": "0030", "label": "Verba C", "reference": "", "value": "300,00"},
                ],
                "bases": [],
            },
        ]
    }

    resultado = tabela.montar_tabela("holerite", value)

    assert resultado.colunas == ["Pág.", "Mês", "Ano", "Salário Base", "Verba A", "Verba C"]
    assert [l.valores for l in resultado.linhas] == [
        ["1", "01", "2020", "1.000,00", "100,00", ""],
        ["2", "02", "2020", "1.000,00", "", ""],
        ["3", "03", "2020", "1.000,00", "", "300,00"],
    ]


def test_holerite_ordem_das_colunas_e_por_primeira_aparicao_nao_alfabetica():
    value = {
        "pages": [
            {
                "page": 1,
                "year": "2020",
                "month": "01",
                "fields": [
                    {"code": "", "label": "Zebra", "reference": "", "value": "1,00"},
                    {"code": "", "label": "Abacaxi", "reference": "", "value": "2,00"},
                ],
                "bases": [],
            }
        ]
    }

    resultado = tabela.montar_tabela("holerite", value)

    assert resultado.colunas == ["Pág.", "Mês", "Ano", "Zebra", "Abacaxi"]


def test_cartao_colunas_pelo_dia_com_mais_batidas_no_documento_inteiro():
    value = {
        "pages": [
            {
                "page": 1,
                "days": [
                    {
                        "date_raw": "01",
                        "punches": [
                            {"kind": "IN", "time_raw": "08:00", "time_hhmm": "08:00"},
                            {"kind": "OUT", "time_raw": "12:00", "time_hhmm": "12:00"},
                        ],
                    }
                ],
            },
            {
                "page": 2,
                "days": [
                    {
                        "date_raw": "02",
                        "punches": [
                            {"kind": "IN", "time_raw": "08:00", "time_hhmm": "08:00"},
                            {"kind": "OUT", "time_raw": "12:00", "time_hhmm": "12:00"},
                            {"kind": "IN", "time_raw": "13:00", "time_hhmm": "13:00"},
                            {"kind": "OUT", "time_raw": "18:00", "time_hhmm": "18:00"},
                        ],
                    }
                ],
            },
        ]
    }

    resultado = tabela.montar_tabela("cartao-ponto", value)

    assert resultado.colunas == ["Data", "Entrada 1", "Saída 1", "Entrada 2", "Saída 2"]
    assert resultado.linhas[0].valores == ["01", "08:00", "12:00", "", ""]
    assert resultado.linhas[1].valores == ["02", "08:00", "12:00", "13:00", "18:00"]


def test_avisos_cartao_batidas_impares_e_incerteza():
    days = [
        {
            "date_raw": "01",
            "punches": [{"kind": "IN", "time_raw": "08:00", "time_hhmm": "08:00"}],
        },
        {
            "date_raw": "02",
            "punches": [
                {"kind": "IN", "time_raw": "??:??", "time_hhmm": "??:??"},
                {"kind": "OUT", "time_raw": "12:00", "time_hhmm": "12:00"},
            ],
        },
    ]

    avisos = tabela.calcular_avisos_cartao(days)

    assert avisos[0] == ["batidas_impares"]
    assert avisos[1] == ["incerto"]


def test_avisos_cartao_data_nao_sequencial():
    days = [
        {"date_raw": "05", "punches": []},
        {"date_raw": "03", "punches": []},
    ]

    avisos = tabela.calcular_avisos_cartao(days)

    assert avisos[0] == []
    assert avisos[1] == ["data_nao_sequencial"]


def test_avisos_cartao_reinicio_de_mes_nao_e_nao_sequencial():
    days = [
        {"date_raw": "30 - SEG", "punches": []},
        {"date_raw": "31 - TER", "punches": []},
        {"date_raw": "1 - QUA", "punches": []},
        {"date_raw": "2 - QUI", "punches": []},
    ]

    avisos = tabela.calcular_avisos_cartao(days)

    assert all("data_nao_sequencial" not in a for a in avisos)


def test_avisos_cartao_marcador_ilegivel_nao_quebra_a_cadeia():
    days = [
        {"date_raw": "05", "punches": []},
        {"date_raw": "?", "punches": []},
        {"date_raw": "06", "punches": []},
    ]

    avisos = tabela.calcular_avisos_cartao(days)

    assert "data_nao_sequencial" not in avisos[0]
    assert "data_nao_sequencial" not in avisos[2]


def test_avisos_holerite_pagina_vazia():
    pages = [{"page": 1, "year": "2020", "month": "01", "fields": [], "bases": []}]

    avisos = tabela.calcular_avisos_holerite(pages)

    assert avisos == [["pagina_vazia"]]


def test_avisos_holerite_mes_nao_sequencial():
    pages = [
        {"page": 1, "year": "2020", "month": "01", "fields": [{"code": "", "label": "X", "reference": "", "value": "1,00"}], "bases": []},
        {"page": 2, "year": "2020", "month": "03", "fields": [{"code": "", "label": "X", "reference": "", "value": "1,00"}], "bases": []},
    ]

    avisos = tabela.calcular_avisos_holerite(pages)

    assert avisos[0] == []
    assert avisos[1] == ["mes_nao_sequencial"]


def test_avisos_holerite_competencia_repetida_nao_e_nao_sequencial():
    pages = [
        {"page": 1, "year": "2018", "month": "08", "fields": [{"code": "", "label": "X", "reference": "", "value": "1,00"}], "bases": []},
        {"page": 1, "year": "2018", "month": "08", "fields": [{"code": "", "label": "Y", "reference": "", "value": "1,00"}], "bases": []},
        {"page": 2, "year": "2018", "month": "09", "fields": [{"code": "", "label": "X", "reference": "", "value": "1,00"}], "bases": []},
    ]

    avisos = tabela.calcular_avisos_holerite(pages)

    assert avisos == [[], [], []]


def test_avisos_holerite_dezembro_para_janeiro_e_consecutivo():
    pages = [
        {"page": 1, "year": "2020", "month": "12", "fields": [{"code": "", "label": "X", "reference": "", "value": "1,00"}], "bases": []},
        {"page": 2, "year": "2021", "month": "01", "fields": [{"code": "", "label": "X", "reference": "", "value": "1,00"}], "bases": []},
    ]

    avisos = tabela.calcular_avisos_holerite(pages)

    assert avisos[1] == []


def test_avisos_holerite_competencia_ilegivel_nao_quebra_a_cadeia():
    pages = [
        {"page": 1, "year": "2020", "month": "01", "fields": [{"code": "", "label": "X", "reference": "", "value": "1,00"}], "bases": []},
        {"page": 2, "year": "?", "month": "?", "fields": [], "bases": []},
        {"page": 3, "year": "2020", "month": "02", "fields": [{"code": "", "label": "X", "reference": "", "value": "1,00"}], "bases": []},
    ]

    avisos = tabela.calcular_avisos_holerite(pages)

    assert "mes_nao_sequencial" not in avisos[2]


def test_cor_da_linha_vermelho_ganha_de_amarelo():
    assert tabela.cor_da_linha(["batidas_impares", "data_nao_sequencial"]) == "vermelho"
    assert tabela.cor_da_linha(["batidas_impares"]) == "amarelo"
    assert tabela.cor_da_linha([]) is None
