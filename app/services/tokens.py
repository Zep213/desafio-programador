import re
import unicodedata

TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")
DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?")
MONEY_RE = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")

MESES = {
    "janeiro": "01", "jan": "01",
    "fevereiro": "02", "fev": "02",
    "marco": "03", "março": "03", "mar": "03",
    "abril": "04", "abr": "04",
    "maio": "05", "mai": "05",
    "junho": "06", "jun": "06",
    "julho": "07", "jul": "07",
    "agosto": "08", "ago": "08",
    "setembro": "09", "set": "09",
    "outubro": "10", "out": "10",
    "novembro": "11", "nov": "11",
    "dezembro": "12", "dez": "12",
}

DIAS_SEMANA = {"dom", "seg", "ter", "qua", "qui", "sex", "sab", "sáb"}


def sem_acento(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )


def _degradar_par(par: str, maximo_dezena: str) -> str:
    if len(par) != 2:
        return "?" * len(par)
    dezena, unidade = par[0], par[1]
    if dezena in maximo_dezena:
        return dezena + "?"
    return "?" + unidade


def normalizar_horario(raw: str) -> str:
    m = TIME_RE.search(raw)
    if not m:
        return "?" * len(raw) if raw else "?"

    hh, mm = m.group(1).zfill(2), m.group(2)

    if "?" in hh or int(hh) > 23:
        hh = _degradar_par(hh, "012") if "?" not in hh else hh
    if "?" in mm or int(mm) > 59:
        mm = _degradar_par(mm, "012345") if "?" not in mm else mm

    return f"{hh}:{mm}"


def _dia_valido(dia: int) -> bool:
    return 1 <= dia <= 31


def _mes_valido(mes: int) -> bool:
    return 1 <= mes <= 12


def normalizar_data(raw: str) -> str | None:
    m = DATE_RE.search(raw)
    if not m:
        return None

    dia, mes, ano = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)

    if not _dia_valido(int(dia)):
        dia = _degradar_par(dia, "0123")
    if not _mes_valido(int(mes)):
        mes = _degradar_par(mes, "01")

    return f"{dia}/{mes}/{ano}" if ano else f"{dia}/{mes}"


def normalizar_dinheiro(raw: str) -> str | None:
    m = MONEY_RE.search(raw)
    return m.group(0) if m else None


def parse_competencia(raw: str) -> tuple[str, str] | None:
    texto = raw.strip()

    m = re.fullmatch(r"(\d{1,2})/(\d{4})", texto)
    if m:
        mes, ano = m.group(1), m.group(2)
        if 1 <= int(mes) <= 12:
            return ano, mes.zfill(2)
        return None

    m = re.fullmatch(r"(\d{4})/(\d{1,2})", texto)
    if m:
        ano, mes = m.group(1), m.group(2)
        if 1 <= int(mes) <= 12:
            return ano, mes.zfill(2)
        return None

    m = re.fullmatch(r"([A-Za-zçÇãÃéÉ]+)[-/](\d{2,4})", texto)
    if m:
        nome_mes, ano = m.group(1), m.group(2)
        mes = MESES.get(sem_acento(nome_mes).lower())
        if mes is None:
            return None
        ano = ("20" + ano) if len(ano) == 2 else ano
        return ano, mes

    return None


def eh_marcador_de_dia(raw: str) -> bool:
    texto = raw.strip()
    m = DATE_RE.match(texto)
    if m:
        return _dia_valido(int(m.group(1))) and _mes_valido(int(m.group(2)))
    m = re.match(r"^(\d{1,2})\b", texto)
    if m and _dia_valido(int(m.group(1))):
        return True
    return False
