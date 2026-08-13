import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("quickfiller")


class PDFCorrompidoError(Exception):
    pass


class OCRFalhouError(Exception):
    pass


class LayoutDesconhecidoError(Exception):
    pass


class DocumentoGrandeDemaisError(Exception):
    pass


class UploadInvalidoError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


MENSAGENS_PIPELINE: dict[type[Exception], str] = {
    PDFCorrompidoError: "O arquivo está corrompido ou não pôde ser aberto.",
    OCRFalhouError: "Não foi possível extrair texto deste documento.",
    LayoutDesconhecidoError: "Não sei ler este documento — layout não reconhecido.",
    DocumentoGrandeDemaisError: "Documento acima do limite de páginas permitido.",
}

MENSAGEM_ERRO_GENERICO = "Erro inesperado ao processar o documento."


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(UploadInvalidoError)
    async def upload_invalido_handler(request: Request, exc: UploadInvalidoError):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def excecao_nao_tratada_handler(request: Request, exc: Exception):
        logger.exception("Erro não tratado em %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno inesperado."},
        )
