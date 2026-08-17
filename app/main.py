import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.controllers.transcricao_controller import router as transcricao_router
from app.errors import registrar_handlers
from app.models.repository import inicializar_schema

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    inicializar_schema()
    yield


app = FastAPI(title="Quick Filler — Desafio Programador", lifespan=lifespan)

registrar_handlers(app)
app.include_router(transcricao_router)
app.mount("/", StaticFiles(directory="app/views/static", html=True), name="static")
