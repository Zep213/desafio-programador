from app.services import tokens


def test_normalizar_horario_valido():
    assert tokens.normalizar_horario("09:03") == "09:03"
    assert tokens.normalizar_horario("8:05") == "08:05"


def test_normalizar_horario_hora_impossivel_degrada_digito():
    assert tokens.normalizar_horario("29:15") == "2?:15"


def test_normalizar_horario_minuto_impossivel_degrada_digito():
    assert tokens.normalizar_horario("14:75") == "14:?5"


def test_normalizar_horario_dezena_implausivel():
    assert tokens.normalizar_horario("93:10") == "?3:10"


def test_normalizar_data_valida():
    assert tokens.normalizar_data("21/05/2019") == "21/05/2019"
    assert tokens.normalizar_data("5/5") == "05/05"


def test_normalizar_data_impossivel_nunca_vira_data_valida():
    resultado = tokens.normalizar_data("38/07")
    assert resultado != "38/07"
    assert "?" in resultado
    assert resultado.endswith("/07")


def test_normalizar_data_mes_impossivel():
    resultado = tokens.normalizar_data("10/13")
    assert "?" in resultado
    assert resultado.startswith("10/")


def test_normalizar_data_texto_sem_data_devolve_none():
    assert tokens.normalizar_data("HE-BCO DE HORAS") is None


def test_normalizar_dinheiro_permanece_string_formato_br():
    valor = tokens.normalizar_dinheiro("Total: 2.389,77 (bruto)")
    assert valor == "2.389,77"
    assert isinstance(valor, str)


def test_normalizar_dinheiro_sem_valor_devolve_none():
    assert tokens.normalizar_dinheiro("sem numero aqui") is None


def test_parse_competencia_mm_aaaa():
    assert tokens.parse_competencia("01/2020") == ("2020", "01")


def test_parse_competencia_aaaa_mm():
    assert tokens.parse_competencia("2020/01") == ("2020", "01")


def test_parse_competencia_mes_abreviado_com_ano_curto():
    assert tokens.parse_competencia("abr-17") == ("2017", "04")


def test_parse_competencia_nome_do_mes_por_extenso():
    assert tokens.parse_competencia("SETEMBRO/2019") == ("2019", "09")


def test_parse_competencia_formato_desconhecido_nunca_chuta():
    assert tokens.parse_competencia("período 3") is None
    assert tokens.parse_competencia("15/2020") is None


def test_eh_marcador_de_dia_numero_simples():
    assert tokens.eh_marcador_de_dia("17") is True
    assert tokens.eh_marcador_de_dia("31") is True


def test_eh_marcador_de_dia_numero_fora_do_intervalo_de_dias():
    assert tokens.eh_marcador_de_dia("32") is False
    assert tokens.eh_marcador_de_dia("00") is False


def test_eh_marcador_de_dia_data_completa():
    assert tokens.eh_marcador_de_dia("21/05/2019") is True


def test_eh_marcador_de_dia_data_completa_impossivel_nao_marca():
    assert tokens.eh_marcador_de_dia("38/07/2019") is False
    assert tokens.eh_marcador_de_dia("10/13/2019") is False


def test_eh_marcador_de_dia_texto_qualquer_nao_marca():
    assert tokens.eh_marcador_de_dia("HE-REMUNERADA") is False
    assert tokens.eh_marcador_de_dia("Assinado") is False
