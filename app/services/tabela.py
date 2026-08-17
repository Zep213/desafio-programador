from dataclasses import dataclass, field

VERMELHO = {"data_nao_sequencial", "mes_nao_sequencial"}
AMARELO = {"batidas_impares", "incerto", "pagina_vazia"}


@dataclass
class LinhaTabela:
    valores: list[str]
    avisos: list[str] = field(default_factory=list)


@dataclass
class Tabela:
    colunas: list[str]
    linhas: list[LinhaTabela]


def cor_da_linha(avisos: list[str]) -> str | None:
    if any(a in VERMELHO for a in avisos):
        return "vermelho"
    if any(a in AMARELO for a in avisos):
        return "amarelo"
    return None


def _numero_dia(date_raw: str) -> int | None:
    texto = date_raw.strip()
    if not texto or texto == "?":
        return None
    primeiro_token = texto.split()[0]
    digitos = "".join(c for c in primeiro_token.split("/")[0] if c.isdigit())
    return int(digitos) if digitos else None


def _tem_incerteza_dia(dia: dict) -> bool:
    if "?" in dia.get("date_raw", ""):
        return True
    return any("?" in p.get("time_hhmm", "") for p in dia.get("punches", []))


def calcular_avisos_cartao(days: list[dict]) -> list[list[str]]:
    avisos: list[list[str]] = []
    ultimo_dia_valido: int | None = None

    for dia in days:
        avisos_dia: list[str] = []
        if len(dia.get("punches", [])) % 2 != 0:
            avisos_dia.append("batidas_impares")
        if _tem_incerteza_dia(dia):
            avisos_dia.append("incerto")

        numero = _numero_dia(dia.get("date_raw", ""))
        if numero is not None:
            if (
                ultimo_dia_valido is not None
                and numero < ultimo_dia_valido
                and ultimo_dia_valido < 28
            ):
                avisos_dia.append("data_nao_sequencial")
            ultimo_dia_valido = numero

        avisos.append(avisos_dia)

    return avisos


def _competencia_legivel(ano: str | None, mes: str | None) -> bool:
    return bool(ano) and bool(mes) and "?" not in ano and "?" not in mes


def _mes_seguinte(ano: str, mes: str) -> tuple[str, str]:
    numero_mes = int(mes)
    if numero_mes == 12:
        return str(int(ano) + 1), "01"
    return ano, str(numero_mes + 1).zfill(2)


def _tem_incerteza_holerite(entrada: dict) -> bool:
    if "?" in entrada.get("year", "") or "?" in entrada.get("month", ""):
        return True
    for campo in entrada.get("fields", []):
        if any("?" in str(campo.get(chave, "")) for chave in ("code", "label", "reference", "value")):
            return True
    for base in entrada.get("bases", []):
        if any("?" in str(base.get(chave, "")) for chave in ("label", "value")):
            return True
    return False


def calcular_avisos_holerite(pages: list[dict]) -> list[list[str]]:
    avisos: list[list[str]] = []
    ultima_competencia: tuple[str, str] | None = None

    for entrada in pages:
        avisos_entrada: list[str] = []
        if not entrada.get("fields") and not entrada.get("bases"):
            avisos_entrada.append("pagina_vazia")
        if _tem_incerteza_holerite(entrada):
            avisos_entrada.append("incerto")

        ano, mes = entrada.get("year"), entrada.get("month")
        if _competencia_legivel(ano, mes):
            atual = (ano, mes)
            if ultima_competencia is not None and atual not in (
                ultima_competencia,
                _mes_seguinte(*ultima_competencia),
            ):
                avisos_entrada.append("mes_nao_sequencial")
            ultima_competencia = atual

        avisos.append(avisos_entrada)

    return avisos


def _tabela_cartao(value: dict) -> Tabela:
    days = [dia for pagina in value.get("pages", []) for dia in pagina.get("days", [])]
    avisos = calcular_avisos_cartao(days)

    max_punches = max((len(d.get("punches", [])) for d in days), default=0)
    pares = -(-max_punches // 2)

    colunas = ["Data"]
    for i in range(1, pares + 1):
        colunas += [f"Entrada {i}", f"Saída {i}"]

    linhas = []
    for dia, avisos_dia in zip(days, avisos):
        punches = dia.get("punches", [])
        valores = [dia.get("date_raw", "")]
        for i in range(pares):
            entrada = punches[2 * i]["time_hhmm"] if 2 * i < len(punches) else ""
            saida = punches[2 * i + 1]["time_hhmm"] if 2 * i + 1 < len(punches) else ""
            valores += [entrada, saida]
        linhas.append(LinhaTabela(valores=valores, avisos=avisos_dia))

    return Tabela(colunas=colunas, linhas=linhas)


def _tabela_holerite(value: dict) -> Tabela:
    entradas = value.get("pages", [])
    avisos = calcular_avisos_holerite(entradas)

    labels_ordenados: list[str] = []
    vistos: set[str] = set()
    for entrada in entradas:
        for campo in entrada.get("fields", []):
            if campo["label"] not in vistos:
                vistos.add(campo["label"])
                labels_ordenados.append(campo["label"])

    colunas = ["Pág.", "Mês", "Ano"] + labels_ordenados

    linhas = []
    for entrada, avisos_entrada in zip(entradas, avisos):
        mapa_valores = {campo["label"]: campo["value"] for campo in entrada.get("fields", [])}
        valores = [str(entrada.get("page", "")), entrada.get("month", ""), entrada.get("year", "")]
        valores += [mapa_valores.get(label, "") for label in labels_ordenados]
        linhas.append(LinhaTabela(valores=valores, avisos=avisos_entrada))

    return Tabela(colunas=colunas, linhas=linhas)


MONTADORES = {
    "cartao-ponto": _tabela_cartao,
    "holerite": _tabela_holerite,
}


def montar_tabela(tipo: str, value: dict) -> Tabela:
    return MONTADORES[tipo](value)
