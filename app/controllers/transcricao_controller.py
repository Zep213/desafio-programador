import os

from fastapi import APIRouter, BackgroundTasks, Form, UploadFile
from fastapi.responses import JSONResponse, Response

from app.errors import UploadInvalidoError
from app.models import repository as repo
from app.models.schemas import AtualizarValueRequest
from app.services import pipeline

router = APIRouter()

TIPOS_VALIDOS = {"cartao-ponto", "holerite"}
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "20"))
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./data/uploads")
CHUNK_SIZE = 1024 * 1024


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
    }


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

    if formato == "json":
        import json

        conteudo = json.dumps(registro["value"], ensure_ascii=False, indent=2)
        return Response(
            content=conteudo,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{id_}.json"'},
        )

    if formato in ("xlsx", "csv"):
        return JSONResponse(
            status_code=501,
            content={"detail": f"Formato '{formato}' disponível no dia 4."},
        )

    return JSONResponse(status_code=422, content={"detail": f"Formato '{formato}' desconhecido."})
