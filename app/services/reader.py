import os
import threading
from dataclasses import dataclass

import pdfplumber

from app.errors import DocumentoGrandeDemaisError, OCRFalhouError, PDFCorrompidoError

DENSIDADE_MINIMA_CHARS = 200
OCR_DPI = 300
PONTOS_POR_POLEGADA = 72
MAX_PAGINAS_DEFAULT = 50
MAX_OCR_CONCORRENTE_DEFAULT = 2

_OCR_SEMAFORO = threading.Semaphore(
    int(os.environ.get("MAX_OCR_CONCORRENTE", MAX_OCR_CONCORRENTE_DEFAULT))
)


@dataclass
class Palavra:
    texto: str
    x0: float
    x1: float
    top: float
    bottom: float
    confianca: float


@dataclass
class PaginaLida:
    page: int
    rota: str
    palavras: list[Palavra]


def ler(caminho: str) -> list[PaginaLida]:
    max_paginas = int(os.environ.get("MAX_PAGINAS", MAX_PAGINAS_DEFAULT))
    try:
        with pdfplumber.open(caminho) as pdf:
            if len(pdf.pages) > max_paginas:
                raise DocumentoGrandeDemaisError(
                    f"Documento tem {len(pdf.pages)} páginas, acima do limite de {max_paginas}."
                )
            paginas_digitais = []
            precisa_ocr = []
            for indice, pagina in enumerate(pdf.pages, start=1):
                texto = pagina.extract_text() or ""
                if len(texto) >= DENSIDADE_MINIMA_CHARS:
                    paginas_digitais.append((indice, _palavras_digitais(pagina)))
                else:
                    precisa_ocr.append(indice)
    except DocumentoGrandeDemaisError:
        raise
    except Exception as exc:
        raise PDFCorrompidoError(str(exc)) from exc

    resultado: dict[int, PaginaLida] = {
        indice: PaginaLida(page=indice, rota="digital", palavras=palavras)
        for indice, palavras in paginas_digitais
    }

    if precisa_ocr:
        for indice, palavras in _paginas_via_ocr(caminho, precisa_ocr):
            resultado[indice] = PaginaLida(page=indice, rota="ocr", palavras=palavras)

    return [resultado[i] for i in sorted(resultado)]


def _palavras_digitais(pagina) -> list[Palavra]:
    return [
        Palavra(
            texto=w["text"],
            x0=w["x0"],
            x1=w["x1"],
            top=w["top"],
            bottom=w["bottom"],
            confianca=100.0,
        )
        for w in pagina.extract_words(use_text_flow=False, keep_blank_chars=False)
    ]


def _paginas_via_ocr(caminho: str, paginas: list[int]) -> list[tuple[int, list[Palavra]]]:
    try:
        import pytesseract
        from pdf2image import convert_from_path
        from pytesseract import Output
    except ImportError as exc:
        raise OCRFalhouError(f"Dependências de OCR indisponíveis: {exc}") from exc

    escala = PONTOS_POR_POLEGADA / OCR_DPI
    saida = []
    for numero_pagina in paginas:
        try:
            with _OCR_SEMAFORO:
                imagens = convert_from_path(
                    caminho, dpi=OCR_DPI, first_page=numero_pagina, last_page=numero_pagina
                )
                imagem = imagens[0].convert("L")
                dados = pytesseract.image_to_data(imagem, lang="por", output_type=Output.DICT)
        except Exception as exc:
            raise OCRFalhouError(f"OCR falhou na página {numero_pagina}: {exc}") from exc

        palavras = []
        for i, texto in enumerate(dados["text"]):
            if not texto.strip():
                continue
            conf = float(dados["conf"][i])
            if conf < 0:
                continue
            x0 = dados["left"][i] * escala
            top = dados["top"][i] * escala
            palavras.append(
                Palavra(
                    texto=texto,
                    x0=x0,
                    x1=x0 + dados["width"][i] * escala,
                    top=top,
                    bottom=top + dados["height"][i] * escala,
                    confianca=conf,
                )
            )
        saida.append((numero_pagina, palavras))
    return saida
