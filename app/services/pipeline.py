import logging
import time

from app.errors import MENSAGEM_ERRO_GENERICO, MENSAGENS_PIPELINE
from app.models import repository as repo
from app.services.extractors.cartao_ponto import CartaoPontoExtractor
from app.services.extractors.holerite import HoleriteExtractor

logger = logging.getLogger("quickfiller")

EXTRACTORS = {
    "cartao-ponto": CartaoPontoExtractor(),
    "holerite": HoleriteExtractor(),
}


def processar(id_: str, caminho: str, tipo: str) -> None:
    try:
        time.sleep(2)
        value = EXTRACTORS[tipo].extract(caminho)
        repo.concluir(id_, value)
    except tuple(MENSAGENS_PIPELINE.keys()) as exc:
        mensagem = MENSAGENS_PIPELINE[type(exc)]
        logger.exception("Falha ao processar transcricao id=%s", id_)
        repo.falhar(id_, mensagem)
    except Exception:
        logger.exception("Erro inesperado ao processar transcricao id=%s", id_)
        repo.falhar(id_, MENSAGEM_ERRO_GENERICO)
