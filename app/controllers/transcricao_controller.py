import logging
import os

from fastapi import APIRouter, BackgroundTasks, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from app.errors import UploadInvalidoError
from app.models import repository as repo
from app.models.schemas import AtualizarValueRequest
from app.services import pipeline, tabela
from app.services.exporters import EXPORTERS

logger = logging.getLogger("quickfiller")

FORMATOS_VALIDOS = {"xlsx", "csv", "json"}

router = APIRouter()

TIPOS_VALIDOS = {"cartao-ponto", "holerite"}
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "20"))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./data/uploads")
RETENCAO_HORAS = float(os.environ.get("RETENCAO_HORAS", "24"))
CHUNK_SIZE = 1024 * 1024


def _limpar_expirados() -> None:
    """Melhor esforço: varre por transcrições mais velhas que RETENCAO_HORAS a
    cada novo upload (não é um cron dedicado — não há infra de agendamento no
    processo hoje). Falha aqui nunca deve derrubar um upload em andamento."""
    try:
        for id_ in repo.listar_ids_expirados(RETENCAO_HORAS):
            caminho = os.path.join(UPLOAD_DIR, f"{id_}.pdf")
            if os.path.exists(caminho):
                os.remove(caminho)
            repo.excluir(id_)
    except Exception:
        logger.exception("Falha ao limpar transcrições expiradas")


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.post("/api/transcricoes", status_code=202)
async def criar_transcricao(
    background_tasks: BackgroundTasks,
    arquivo: UploadFile,
    tipo: str = Form(...),
):
    if tipo not in TIPOS_VALIDOS:
        raise UploadInvalidoError(422, f"tipo inválido: '{tipo}'. Use 'cartao-ponto' ou 'holerite'.")

    _limpar_expirados()

    limite_bytes = MAX_UPLOAD_MB * 1024 * 1024
    primeiro_chunk = await arquivo.read(CHUNK_SIZE)
    if not primeiro_chunk.startswith(b"%PDF"):
        raise UploadInvalidoError(400, "O arquivo enviado não é um PDF válido.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    id_ = repo.criar(tipo)
    caminho = os.path.join(UPLOAD_DIR, f"{id_}.pdf")

    total = 0
    try:
        with open(caminho, "wb") as destino:
            chunk = primeiro_chunk
            while chunk:
                total += len(chunk)
                if total > limite_bytes:
                    raise UploadInvalidoError(
                        413, f"Arquivo acima do limite de {MAX_UPLOAD_MB}MB."
                    )
                destino.write(chunk)
                chunk = await arquivo.read(CHUNK_SIZE)
    except UploadInvalidoError:
        if os.path.exists(caminho):
            os.remove(caminho)
        repo.falhar(id_, "Upload recusado.")
        raise

    background_tasks.add_task(pipeline.processar, id_, caminho, tipo)
    return JSONResponse(status_code=202, content={"id": id_})


def _calcular_avisos(tipo: str, value: dict | None) -> list[list[str]] | None:
    """Avisos nunca são armazenados — recalculados a cada resposta a partir do
    'value' atual, com as MESMAS funções que os exporters usam (services/tabela.py),
    na mesma ordem de linhas que a tabela/planilha (páginas então dias, sem reordenar)."""
    if value is None:
        return None
    if tipo == "cartao-ponto":
        dias = [dia for pagina in value.get("pages", []) for dia in pagina.get("days", [])]
        return tabela.calcular_avisos_cartao(dias)
    return tabela.calcular_avisos_holerite(value.get("pages", []))


@router.get("/api/transcricoes/{id_}")
async def obter_transcricao(id_: str):
    registro = repo.buscar(id_)
    if registro is None:
        return JSONResponse(status_code=404, content={"detail": f"Transcrição '{id_}' não encontrada."})
    return {
        "id": registro["id"],
        "tipo": registro["tipo"],
        "status": registro["status"],
        "erro": registro["erro"],
        "value": registro["value"],
        "avisos": _calcular_avisos(registro["tipo"], registro["value"]),
    }


@router.get("/api/transcricoes/{id_}/arquivo")
async def baixar_arquivo_original(id_: str):
    registro = repo.buscar(id_)
    if registro is None:
        return JSONResponse(status_code=404, content={"detail": f"Transcrição '{id_}' não encontrada."})

    caminho = os.path.join(UPLOAD_DIR, f"{id_}.pdf")
    if not os.path.exists(caminho):
        return JSONResponse(status_code=404, content={"detail": "Arquivo original não está mais disponível."})

    return FileResponse(caminho, media_type="application/pdf")


@router.put("/api/transcricoes/{id_}")
async def atualizar_transcricao(id_: str, body: AtualizarValueRequest):
    registro = repo.buscar(id_)
    if registro is None:
        return JSONResponse(status_code=404, content={"detail": f"Transcrição '{id_}' não encontrada."})
    if registro["status"] == "processando":
        return JSONResponse(
            status_code=409,
            content={"detail": "Transcrição ainda em processamento — aguarde para editar."},
        )
    repo.substituir_value(id_, body.value)
    return repo.buscar(id_)


@router.get("/api/transcricoes/{id_}/planilha")
async def baixar_planilha(id_: str, formato: str = "json"):
    registro = repo.buscar(id_)
    if registro is None:
        return JSONResponse(status_code=404, content={"detail": f"Transcrição '{id_}' não encontrada."})

    if formato not in FORMATOS_VALIDOS:
        return JSONResponse(status_code=422, content={"detail": f"Formato '{formato}' desconhecido."})

    if registro["value"] is None:
        return JSONResponse(
            status_code=409,
            content={"detail": "Transcrição ainda não tem dados para gerar planilha."},
        )

    conteudo, mimetype = EXPORTERS[registro["tipo"]].export(registro["value"], formato)
    return Response(
        content=conteudo,
        media_type=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{id_}.{formato}"'},
    )
