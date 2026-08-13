import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "./data/app.db")


def _garantir_diretorio() -> None:
    diretorio = os.path.dirname(DB_PATH)
    if diretorio:
        os.makedirs(diretorio, exist_ok=True)


@contextmanager
def _conexao():
    _garantir_diretorio()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def inicializar_schema() -> None:
    with _conexao() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transcricoes (
                id TEXT PRIMARY KEY,
                tipo TEXT NOT NULL,
                status TEXT NOT NULL,
                erro TEXT,
                value TEXT,
                criado_em TEXT NOT NULL
            )
            """
        )


def criar(tipo: str) -> str:
    id_ = uuid.uuid4().hex[:12]
    criado_em = datetime.now(timezone.utc).isoformat()
    with _conexao() as conn:
        conn.execute(
            "INSERT INTO transcricoes (id, tipo, status, erro, value, criado_em) "
            "VALUES (?, ?, 'processando', NULL, NULL, ?)",
            (id_, tipo, criado_em),
        )
    return id_


def buscar(id_: str) -> dict | None:
    with _conexao() as conn:
        linha = conn.execute(
            "SELECT id, tipo, status, erro, value, criado_em FROM transcricoes WHERE id = ?",
            (id_,),
        ).fetchone()
    if linha is None:
        return None
    return {
        "id": linha["id"],
        "tipo": linha["tipo"],
        "status": linha["status"],
        "erro": linha["erro"],
        "value": json.loads(linha["value"]) if linha["value"] is not None else None,
        "criado_em": linha["criado_em"],
    }


def concluir(id_: str, value: dict) -> None:
    with _conexao() as conn:
        conn.execute(
            "UPDATE transcricoes SET status = 'concluido', value = ?, erro = NULL WHERE id = ?",
            (json.dumps(value, ensure_ascii=False), id_),
        )


def falhar(id_: str, mensagem: str) -> None:
    with _conexao() as conn:
        conn.execute(
            "UPDATE transcricoes SET status = 'erro', erro = ? WHERE id = ?",
            (mensagem, id_),
        )


def substituir_value(id_: str, value: dict) -> None:
    with _conexao() as conn:
        conn.execute(
            "UPDATE transcricoes SET value = ? WHERE id = ?",
            (json.dumps(value, ensure_ascii=False), id_),
        )
