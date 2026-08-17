import os

from app.errors import LayoutDesconhecidoError
from app.services import colunas as colunas_util
from app.services import reader, tokens
from app.services.extractors.base import Extractor
from app.services.reader import Palavra

LIMIAR_CONFIANCA_OCR_DEFAULT = 65.0
LIMIAR_CONFIANCA_OCR = float(os.environ.get("OCR_CONF_THRESHOLD", LIMIAR_CONFIANCA_OCR_DEFAULT))

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
            linhas = colunas_util.agrupar_em_linhas(pagina.palavras)
            cabecalho = _localizar_cabecalho(linhas)

            if cabecalho is not None:
                colunas_atuais = colunas_util.colunas_do_cabecalho(cabecalho["linha"], SINONIMOS_COLUNA)
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


def _localizar_cabecalho(linhas: list[list[Palavra]]) -> dict | None:
    for linha in linhas:
        if any(tokens.sem_acento(p.texto).lower() == "dia" for p in linha):
            return {"linha": linha, "top": linha[0].top}
    return None


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
            (colunas_util.papel_da_coluna((p.x0 + p.x1) / 2, colunas), p) for p in linha
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


GAP_MINIMO_AREA_DE_TOTAIS = 25.0


def _limite_area_de_batidas(horarios: list[Palavra]) -> float:
    """Sem cabeçalho pra apontar onde a coluna de batida termina e a de totais
    (H.Ext, Atraso, Falta, Ad.Not, Abono...) começa, usa a própria geometria da
    linha: as batidas de verdade ficam com espaçamento regular entre si, e há um
    salto horizontal bem maior antes do bloco de totais. Sem esse salto claro
    (linha só com 0 ou 1 horário, ou espaçamento uniforme), não corta nada — é
    melhor manter tudo do que arriscar cortar batida de verdade."""
    if len(horarios) < 2:
        return float("inf")

    ordenadas = sorted(horarios, key=lambda p: p.x0)
    gaps = [ordenadas[i + 1].x0 - ordenadas[i].x1 for i in range(len(ordenadas) - 1)]
    maior = max(gaps)
    indice_maior = gaps.index(maior)

    outros = [g for i, g in enumerate(gaps) if i != indice_maior]
    media_outros = (sum(outros) / len(outros)) if outros else 0.0

    salto_e_dominante = maior >= GAP_MINIMO_AREA_DE_TOTAIS and maior > 2 * media_outros
    if not salto_e_dominante:
        return float("inf")
    return ordenadas[indice_maior + 1].x0


def _extrair_dias_fallback(linhas: list[list[Palavra]]) -> list[dict]:
    dias: list[dict] = []
    dia_atual: dict | None = None

    for linha in linhas:
        primeira = linha[0]
        eh_novo_dia = tokens.eh_marcador_de_dia(primeira.texto)
        todos_horarios = [p for p in linha if tokens.TIME_RE.search(p.texto)]
        limite = _limite_area_de_batidas(todos_horarios)
        horarios = [p for p in todos_horarios if p.x0 < limite]

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
