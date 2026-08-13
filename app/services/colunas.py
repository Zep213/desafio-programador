import bisect

from app.services import tokens
from app.services.reader import Palavra

TOLERANCIA_LINHA_PADRAO = 3.0


def agrupar_em_linhas(palavras: list[Palavra], tolerancia: float = TOLERANCIA_LINHA_PADRAO) -> list[list[Palavra]]:
    ordenadas = sorted(palavras, key=lambda p: (p.top, p.x0))
    linhas: list[list[Palavra]] = []
    linha_atual: list[Palavra] = []
    top_referencia = None

    for palavra in ordenadas:
        if top_referencia is None or abs(palavra.top - top_referencia) <= tolerancia:
            linha_atual.append(palavra)
            top_referencia = top_referencia if top_referencia is not None else palavra.top
        else:
            linhas.append(sorted(linha_atual, key=lambda p: p.x0))
            linha_atual = [palavra]
            top_referencia = palavra.top

    if linha_atual:
        linhas.append(sorted(linha_atual, key=lambda p: p.x0))

    return linhas


def colunas_do_cabecalho(linha_cabecalho: list[Palavra], sinonimos: dict[str, str]) -> list[dict]:
    colunas = []
    for palavra in linha_cabecalho:
        papel = sinonimos.get(tokens.sem_acento(palavra.texto).lower(), "outro")
        colunas.append({"papel": papel, "centro": (palavra.x0 + palavra.x1) / 2})
    colunas.sort(key=lambda c: c["centro"])
    return colunas


def papel_da_coluna(centro_palavra: float, colunas: list[dict]) -> str:
    centros = [c["centro"] for c in colunas]
    fronteiras = [(centros[i] + centros[i + 1]) / 2 for i in range(len(centros) - 1)]
    indice = bisect.bisect_right(fronteiras, centro_palavra)
    return colunas[indice]["papel"]
