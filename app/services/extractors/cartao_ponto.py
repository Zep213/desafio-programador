import bisect

from app.errors import LayoutDesconhecidoError
from app.services import reader, tokens
from app.services.extractors.base import Extractor
from app.services.reader import Palavra

TOLERANCIA_LINHA = 3.0
LIMIAR_CONFIANCA_OCR = 65.0

SINONIMOS_COLUNA = {
    "dia": "dia",
    "data": "dia",
    "semana": "semana",
    "entrada": "entrada",
    "ent": "entrada",
    "saida": "saida",
    "sai": "saida",
}


class CartaoPontoExtractor(Extractor):
    def extract(self, caminho: str) -> dict:
        paginas_lidas = reader.ler(caminho)

        colunas_atuais: list[dict] | None = None
        pages: list[dict] = []

        for pagina in paginas_lidas:
            linhas = _agrupar_em_linhas(pagina.palavras)
            cabecalho = _localizar_cabecalho(linhas)

            if cabecalho is not None:
                colunas_atuais = _colunas_do_cabecalho(cabecalho["linha"])
                linhas_de_dados = [l for l in linhas if l[0].top > cabecalho["top"]]
            else:
                linhas_de_dados = linhas

            if colunas_atuais is not None:
                days = _extrair_dias_por_coluna(linhas_de_dados, colunas_atuais)
            else:
                days = _extrair_dias_fallback(linhas_de_dados)

            pages.append({"page": pagina.page, "days": days})

        if all(len(p["days"]) == 0 for p in pages):
            raise LayoutDesconhecidoError(
                "Nenhum dia reconhecido em nenhuma página — layout não identificado."
            )

        return {"pages": pages}


def _agrupar_em_linhas(palavras: list[Palavra]) -> list[list[Palavra]]:
    ordenadas = sorted(palavras, key=lambda p: (p.top, p.x0))
    linhas: list[list[Palavra]] = []
    linha_atual: list[Palavra] = []
    top_referencia = None

    for palavra in ordenadas:
        if top_referencia is None or abs(palavra.top - top_referencia) <= TOLERANCIA_LINHA:
            linha_atual.append(palavra)
            top_referencia = top_referencia if top_referencia is not None else palavra.top
        else:
            linhas.append(sorted(linha_atual, key=lambda p: p.x0))
            linha_atual = [palavra]
            top_referencia = palavra.top

    if linha_atual:
        linhas.append(sorted(linha_atual, key=lambda p: p.x0))

    return linhas


def _localizar_cabecalho(linhas: list[list[Palavra]]) -> dict | None:
    for linha in linhas:
        if any(tokens.sem_acento(p.texto).lower() == "dia" for p in linha):
            return {"linha": linha, "top": linha[0].top}
    return None


def _colunas_do_cabecalho(linha_cabecalho: list[Palavra]) -> list[dict]:
    colunas = []
    for palavra in linha_cabecalho:
        papel = SINONIMOS_COLUNA.get(tokens.sem_acento(palavra.texto).lower(), "outro")
        colunas.append({"papel": papel, "centro": (palavra.x0 + palavra.x1) / 2})
    colunas.sort(key=lambda c: c["centro"])
    return colunas


def _papel_da_coluna(centro_palavra: float, colunas: list[dict]) -> str:
    centros = [c["centro"] for c in colunas]
    fronteiras = [(centros[i] + centros[i + 1]) / 2 for i in range(len(centros) - 1)]
    indice = bisect.bisect_right(fronteiras, centro_palavra)
    return colunas[indice]["papel"]


def _tempos_da_palavra(palavra: Palavra) -> list[tuple[str, str]]:
    tempos = []
    for m in tokens.TIME_RE.finditer(palavra.texto):
        if palavra.confianca < LIMIAR_CONFIANCA_OCR:
            hhmm = "??:??"
        else:
            hhmm = tokens.normalizar_horario(m.group(0))
        tempos.append((palavra.texto, hhmm))
    return tempos


def _extrair_dias_por_coluna(linhas: list[list[Palavra]], colunas: list[dict]) -> list[dict]:
    dias: list[dict] = []
    dia_atual: dict | None = None

    for linha in linhas:
        classificada = [
            (_papel_da_coluna((p.x0 + p.x1) / 2, colunas), p) for p in linha
        ]

        marcador = [p for papel, p in classificada if papel in ("dia", "semana")]
        eh_novo_dia = bool(marcador) and tokens.eh_marcador_de_dia(marcador[0].texto)

        entradas = [p for papel, p in classificada if papel == "entrada" and tokens.TIME_RE.search(p.texto)]
        saidas = [p for papel, p in classificada if papel == "saida" and tokens.TIME_RE.search(p.texto)]

        if not eh_novo_dia and not entradas and not saidas:
            continue

        if eh_novo_dia:
            dia_atual = {"date_raw": " ".join(p.texto for p in marcador), "punches": []}
            dias.append(dia_atual)
        elif dia_atual is None:
            dia_atual = {"date_raw": "?", "punches": []}
            dias.append(dia_atual)

        palavras_com_papel = sorted(
            [("entrada", p) for p in entradas] + [("saida", p) for p in saidas],
            key=lambda item: item[1].x0,
        )
        for papel, palavra in palavras_com_papel:
            tempos = _tempos_da_palavra(palavra)
            if len(tempos) >= 2:
                kinds = ["IN", "OUT"] * (len(tempos) // 2 + 1)
            else:
                kinds = ["IN" if papel == "entrada" else "OUT"]
            for kind, (time_raw, time_hhmm) in zip(kinds, tempos):
                dia_atual["punches"].append({"kind": kind, "time_raw": time_raw, "time_hhmm": time_hhmm})

    return dias


def _extrair_dias_fallback(linhas: list[list[Palavra]]) -> list[dict]:
    dias: list[dict] = []
    dia_atual: dict | None = None

    for linha in linhas:
        primeira = linha[0]
        eh_novo_dia = tokens.eh_marcador_de_dia(primeira.texto)
        horarios = [p for p in linha if tokens.TIME_RE.search(p.texto)]

        if not eh_novo_dia and not horarios:
            continue

        if eh_novo_dia:
            dia_atual = {"date_raw": primeira.texto, "punches": []}
            dias.append(dia_atual)
            horarios = [p for p in horarios if p is not primeira]
        elif dia_atual is None:
            dia_atual = {"date_raw": "?", "punches": []}
            dias.append(dia_atual)

        contador = 0
        for palavra in horarios:
            for time_raw, time_hhmm in _tempos_da_palavra(palavra):
                kind = "IN" if contador % 2 == 0 else "OUT"
                dia_atual["punches"].append({"kind": kind, "time_raw": time_raw, "time_hhmm": time_hhmm})
                contador += 1

    return dias
