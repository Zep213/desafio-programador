import threading

from app.models import repository as repo


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_post_tipo_invalido_422(client, pdf_valido):
    resp = client.post(
        "/api/transcricoes",
        files={"arquivo": ("doc.pdf", pdf_valido, "application/pdf")},
        data={"tipo": "invalido"},
    )
    assert resp.status_code == 422


def test_post_arquivo_nao_pdf_400(client):
    conteudo = b"isto e um texto qualquer, nao um pdf"
    resp = client.post(
        "/api/transcricoes",
        files={"arquivo": ("fake.pdf", conteudo, "application/pdf")},
        data={"tipo": "cartao-ponto"},
    )
    assert resp.status_code == 400


def test_post_arquivo_acima_do_limite_413(client):
    conteudo = b"%PDF-1.4\n" + b"0" * (2 * 1024 * 1024)
    resp = client.post(
        "/api/transcricoes",
        files={"arquivo": ("grande.pdf", conteudo, "application/pdf")},
        data={"tipo": "cartao-ponto"},
    )
    assert resp.status_code == 413


def test_get_id_inexistente_404(client):
    resp = client.get("/api/transcricoes/nao-existe")
    assert resp.status_code == 404
    assert "não encontrada" in resp.json()["detail"]


def test_ciclo_completo_polling_ate_concluido(client, monkeypatch, pdf_valido):
    entrou_no_pipeline = threading.Event()
    pode_continuar = threading.Event()

    def sleep_controlado(_segundos):
        entrou_no_pipeline.set()
        pode_continuar.wait(timeout=5)

    monkeypatch.setattr("app.services.pipeline.time.sleep", sleep_controlado)

    ids_criados: list[str] = []
    criar_original = repo.criar

    def criar_espiao(tipo):
        id_ = criar_original(tipo)
        ids_criados.append(id_)
        return id_

    monkeypatch.setattr("app.models.repository.criar", criar_espiao)

    resultado = {}

    def enviar():
        resultado["resp"] = client.post(
            "/api/transcricoes",
            files={"arquivo": ("holerite.pdf", pdf_valido, "application/pdf")},
            data={"tipo": "holerite"},
        )

    t = threading.Thread(target=enviar)
    t.start()

    assert entrou_no_pipeline.wait(timeout=5), "pipeline não começou a processar"
    assert ids_criados, "id não foi criado antes do processamento"
    id_ = ids_criados[0]

    intermediario = client.get(f"/api/transcricoes/{id_}")
    assert intermediario.status_code == 200
    assert intermediario.json()["status"] == "processando"
    assert intermediario.json()["value"] is None

    pode_continuar.set()
    t.join(timeout=5)

    assert resultado["resp"].status_code == 202
    assert resultado["resp"].json()["id"] == id_

    final = client.get(f"/api/transcricoes/{id_}")
    assert final.status_code == 200
    corpo = final.json()
    assert corpo["status"] == "concluido"
    assert corpo["erro"] is None
    assert corpo["value"]["pages"][0]["year"] == "2024"


def test_put_substitui_value_e_get_reflete(client, pdf_valido, monkeypatch):
    id_ = repo.criar("cartao-ponto")
    repo.concluir(id_, {"pages": [{"page": 1, "days": []}]})

    novo_value = {"pages": [{"page": 1, "days": [{"date_raw": "05/05/2024", "punches": []}]}]}
    resp = client.put(f"/api/transcricoes/{id_}", json={"value": novo_value})
    assert resp.status_code == 200
    assert resp.json()["value"] == novo_value

    seguinte = client.get(f"/api/transcricoes/{id_}")
    assert seguinte.json()["value"] == novo_value


def test_put_em_processando_409(client):
    id_ = repo.criar("holerite")
    resp = client.put(f"/api/transcricoes/{id_}", json={"value": {"pages": []}})
    assert resp.status_code == 409


def test_planilha_formato_json_devolve_value_editado(client):
    id_ = repo.criar("holerite")
    value = {"pages": [{"page": 1, "year": "2024", "month": "03", "fields": [], "bases": []}]}
    repo.concluir(id_, value)

    resp = client.get(f"/api/transcricoes/{id_}/planilha?formato=json")
    assert resp.status_code == 200
    assert resp.json() == value


def test_planilha_xlsx_e_csv_ainda_nao_implementados_501(client):
    id_ = repo.criar("holerite")
    repo.concluir(id_, {"pages": []})

    for formato in ("xlsx", "csv"):
        resp = client.get(f"/api/transcricoes/{id_}/planilha?formato={formato}")
        assert resp.status_code == 501
