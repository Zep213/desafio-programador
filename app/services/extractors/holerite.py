import re

from app.errors import LayoutDesconhecidoError
from app.services import colunas as colunas_util
from app.services import reader, tokens
from app.services.extractors.base import Extractor
from app.services.reader import Palavra

SINONIMOS_COLUNA = {
    "verba": "codigo",
    "cod": "codigo",
    "cod.": "codigo",
    "codigo": "codigo",
    "nome": "nome",
    "descricao": "nome",
    "valor": "valor",
    "proventos": "valor",
    "descontos": "valor",
    "qtde": "referencia",
    "ref": "referencia",
    "unidade": "referencia",
    "base": "referencia",
    "saldo": "referencia",
    "beneficio": "referencia",
}

GATILHOS_COMPETENCIA = ("mes", "periodo", "competencia")

PALAVRAS_CHAVE_BASES = (
    "base",
    "total",
    "liquido",
    "fgts",
    "margem",
    "consignac",
    "bruto",
)


class HoleriteExtractor(Extractor):
    def extract(self, caminho: str) -> dict:
        paginas_lidas = reader.ler(caminho)

        colunas_atuais: list[dict] | None = None
        pages: list[dict] = []

        for pagina in paginas_lidas:
            linhas = colunas_util.agrupar_em_linhas(pagina.palavras)
            cabecalho = _localizar_cabecalho(linhas)

            if cabecalho is not None:
                colunas_atuais = colunas_util.colunas_do_cabecalho(cabecalho["linha"], SINONIMOS_COLUNA)

            blocos = _dividir_por_competencia(linhas)

            if not blocos:
                pages.append({"page": pagina.page, "year": "?", "month": "?", "fields": [], "bases": []})
                continue

            for competencia, linhas_bloco in blocos:
                year, month = competencia
                fields, bases = _extrair_fields_e_bases(linhas_bloco, colunas_atuais)
                pages.append(
                    {"page": pagina.page, "year": year, "month": month, "fields": fields, "bases": bases}
                )

        if all(len(p["fields"]) == 0 and len(p["bases"]) == 0 for p in pages):
            raise LayoutDesconhecidoError(
                "Nenhuma verba nem base reconhecida em nenhuma página — layout não identificado."
            )

        return {"pages": pages}


def _localizar_cabecalho(linhas: list[list[Palavra]]) -> dict | None:
    for linha in linhas:
        papeis = [SINONIMOS_COLUNA.get(tokens.sem_acento(p.texto).lower()) for p in linha]
        reconhecidos = [p for p in papeis if p is not None]
        if len(reconhecidos) >= 2:
            return {"linha": linha, "top": linha[0].top}
    return None


def _competencia_na_linha(linha: list[Palavra]) -> tuple[str, str] | None:
    for indice, palavra in enumerate(linha):
        normalizado = tokens.sem_acento(palavra.texto).lower()
        if any(normalizado.startswith(gatilho) for gatilho in GATILHOS_COMPETENCIA):
            for candidata in linha[indice : indice + 4]:
                resultado = tokens.parse_competencia(candidata.texto.strip(":"))
                if resultado:
                    return resultado
    return None


def _dividir_por_competencia(linhas: list[list[Palavra]]) -> list[tuple[tuple[str, str], list[list[Palavra]]]]:
    blocos: list[tuple[tuple[str, str], list[list[Palavra]]]] = []
    linhas_do_bloco: list[list[Palavra]] | None = None

    for linha in linhas:
        competencia = _competencia_na_linha(linha)
        if competencia:
            linhas_do_bloco = []
            blocos.append((competencia, linhas_do_bloco))
        elif linhas_do_bloco is not None:
            linhas_do_bloco.append(linha)

    return blocos


def _linha_tem_dois_pontos(linha: list[Palavra]) -> bool:
    return any(p.texto == ":" or (p.texto.endswith(":") and len(p.texto) > 1) for p in linha)


def _parece_referencia(texto: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(?:[.,]\d+)*", texto))


def _parece_codigo(texto: str) -> bool:
    return bool(re.fullmatch(r"/?[A-Za-z0-9][A-Za-z0-9.\-]{0,5}", texto)) and any(c.isdigit() for c in texto)


def _eh_rotulo_de_base(label: str) -> bool:
    normalizado = tokens.sem_acento(label).lower().replace(" ", "").replace(".", "")
    return any(chave in normalizado for chave in PALAVRAS_CHAVE_BASES)


def _pares_rotulo_valor(linha: list[Palavra]) -> list[tuple[str, str]]:
    pares = []
    buffer: list[str] = []
    i = 0

    while i < len(linha):
        texto = linha[i].texto

        if texto == ":":
            rotulo = " ".join(buffer).strip()
            buffer = []
            valor = tokens.normalizar_dinheiro(linha[i + 1].texto) if i + 1 < len(linha) else None
            if valor is not None and rotulo:
                pares.append((rotulo, valor))
                i += 2
                continue
            i += 1
            continue

        if texto.endswith(":") and len(texto) > 1:
            buffer.append(texto[:-1])
            rotulo = " ".join(buffer).strip()
            buffer = []
            valor = tokens.normalizar_dinheiro(linha[i + 1].texto) if i + 1 < len(linha) else None
            if valor is not None and rotulo:
                pares.append((rotulo, valor))
                i += 2
                continue
            i += 1
            continue

        buffer.append(texto)
        i += 1

    return pares


def _extrair_fields_e_bases(
    linhas: list[list[Palavra]], colunas: list[dict] | None
) -> tuple[list[dict], list[dict]]:
    fields: list[dict] = []
    bases: list[dict] = []

    if colunas is not None:
        for linha in linhas:
            if _linha_tem_dois_pontos(linha):
                continue

            classificada = [
                (colunas_util.papel_da_coluna((p.x0 + p.x1) / 2, colunas), p) for p in linha
            ]
            codigos_brutos = [p for papel, p in classificada if papel == "codigo"]
            nomes = [p for papel, p in classificada if papel == "nome"]
            referencias_brutas = [p for papel, p in classificada if papel == "referencia"]

            codigos = [p for p in codigos_brutos if _parece_codigo(p.texto)]
            referencias = [p for p in referencias_brutas if _parece_referencia(p.texto)]
            nomes_completos = sorted(
                nomes
                + [p for p in codigos_brutos if not _parece_codigo(p.texto)]
                + [p for p in referencias_brutas if not _parece_referencia(p.texto)],
                key=lambda p: p.x0,
            )
            valores = [
                p
                for papel, p in classificada
                if papel == "valor" and tokens.normalizar_dinheiro(p.texto)
            ]

            if not valores or not nomes_completos:
                continue

            label = " ".join(p.texto for p in nomes_completos)
            code = codigos[0].texto if codigos else ""
            reference = referencias[0].texto if referencias else ""

            for palavra_valor in sorted(valores, key=lambda p: p.x0):
                value = tokens.normalizar_dinheiro(palavra_valor.texto)
                if _eh_rotulo_de_base(label):
                    bases.append({"label": label, "value": value})
                else:
                    fields.append({"code": code, "label": label, "reference": reference, "value": value})

    for linha in linhas:
        for rotulo, valor in _pares_rotulo_valor(linha):
            bases.append({"label": rotulo, "value": valor})

    return fields, bases
