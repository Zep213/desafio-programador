"use strict";

const MOTIVOS_AVISO = {
  batidas_impares: "Batidas ímpares — falta uma entrada ou uma saída nesse dia.",
  incerto: "Tem pelo menos um caractere que não foi lido com segurança (?).",
  data_nao_sequencial: "A data desta linha quebra a sequência do documento.",
  pagina_vazia: "A página existe no PDF, mas nenhum dado foi extraído dela.",
  mes_nao_sequencial: "A competência não é o mês seguinte à página anterior.",
};

const VERMELHO = new Set(["data_nao_sequencial", "mes_nao_sequencial"]);
const AMARELO = new Set(["batidas_impares", "incerto", "pagina_vazia"]);

function corDaLinha(avisos) {
  if (avisos.some((a) => VERMELHO.has(a))) return "linha-vermelha";
  if (avisos.some((a) => AMARELO.has(a))) return "linha-amarela";
  return null;
}

const els = {
  formUpload: document.getElementById("form-upload"),
  inputArquivo: document.getElementById("input-arquivo"),
  inputTipo: document.getElementById("input-tipo"),
  btnEnviar: document.getElementById("btn-enviar"),

  painelUpload: document.getElementById("painel-upload"),
  painelProgresso: document.getElementById("painel-progresso"),
  painelErro: document.getElementById("painel-erro"),
  mensagemErro: document.getElementById("mensagem-erro"),
  btnTentarOutro: document.getElementById("btn-tentar-outro"),
  painelRevisao: document.getElementById("painel-revisao"),

  embedPdf: document.getElementById("embed-pdf"),
  tabelaRevisao: document.getElementById("tabela-revisao"),
  motivosAviso: document.getElementById("motivos-aviso"),

  btnSalvar: document.getElementById("btn-salvar"),
  statusSalvar: document.getElementById("status-salvar"),
  botoesDownload: document.querySelectorAll("[data-formato]"),
};

const POLL_INTERVALO_MS = 2000;

const estado = {
  id: null,
  tipo: null,
  value: null,
  linhas: [], // [{ refs: {...}, avisos: [...] }] — uma entrada por linha da tabela
  sujo: false, // há edição não salva desde o último PUT bem sucedido
  pollTimer: null,
};

function pararPolling() {
  if (estado.pollTimer !== null) {
    clearInterval(estado.pollTimer);
    estado.pollTimer = null;
  }
}

window.addEventListener("beforeunload", pararPolling);

function mostrarPainel(nome) {
  for (const p of [els.painelUpload, els.painelProgresso, els.painelErro, els.painelRevisao]) {
    p.classList.add("hidden");
  }
  nome.classList.remove("hidden");
}

async function enviarUpload(ev) {
  ev.preventDefault();
  const arquivo = els.inputArquivo.files[0];
  if (!arquivo) return;

  const dados = new FormData();
  dados.append("arquivo", arquivo);
  dados.append("tipo", els.inputTipo.value);

  els.btnEnviar.disabled = true;
  try {
    const resp = await fetch("/api/transcricoes", { method: "POST", body: dados });
    const corpo = await resp.json();
    if (!resp.ok) {
      mostrarErro(corpo.detail || "Não foi possível enviar o arquivo.");
      return;
    }
    estado.id = corpo.id;
    estado.tipo = els.inputTipo.value;
    mostrarPainel(els.painelProgresso);
    iniciarPolling();
  } catch (e) {
    mostrarErro("Falha de rede ao enviar o arquivo.");
  } finally {
    els.btnEnviar.disabled = false;
  }
}

function iniciarPolling() {
  pararPolling(); // nunca deixa mais de um polling ativo ao mesmo tempo
  const verificar = async () => {
    try {
      const resp = await fetch(`/api/transcricoes/${estado.id}`);
      const corpo = await resp.json();
      if (!resp.ok) {
        pararPolling();
        mostrarErro(corpo.detail || "Transcrição não encontrada.");
        return;
      }
      if (corpo.status === "processando") return;

      pararPolling();
      if (corpo.status === "erro") {
        mostrarErro(corpo.erro || "Erro desconhecido ao processar o documento.");
        return;
      }
      abrirRevisao(corpo);
    } catch (e) {
      pararPolling();
      mostrarErro("Falha de rede ao acompanhar o processamento.");
    }
  };

  estado.pollTimer = setInterval(verificar, POLL_INTERVALO_MS);
  verificar(); // primeira checagem imediata, sem esperar o intervalo inteiro
}

function mostrarErro(mensagem) {
  els.mensagemErro.textContent = mensagem;
  mostrarPainel(els.painelErro);
}

function voltarParaUpload() {
  pararPolling();
  els.formUpload.reset();
  mostrarPainel(els.painelUpload);
}

function montarLinhasCartao(value) {
  const dias = [];
  (value.pages || []).forEach((pagina, pIdx) => {
    (pagina.days || []).forEach((dia, dIdx) => {
      dias.push({ dia, pIdx, dIdx });
    });
  });

  const maxPunches = dias.reduce((m, { dia }) => Math.max(m, (dia.punches || []).length), 0);
  const pares = Math.ceil(maxPunches / 2);

  const colunas = ["Data"];
  for (let i = 1; i <= pares; i++) colunas.push(`Entrada ${i}`, `Saída ${i}`);

  const linhas = dias.map(({ dia, pIdx, dIdx }) => {
    const celulas = [{ texto: dia.date_raw || "", campo: { tipo: "date_raw", pIdx, dIdx } }];
    for (let i = 0; i < pares; i++) {
      const punches = dia.punches || [];
      const entrada = punches[2 * i];
      const saida = punches[2 * i + 1];
      celulas.push({ texto: entrada ? entrada.time_hhmm : "", campo: { tipo: "punch", pIdx, dIdx, idx: 2 * i } });
      celulas.push({ texto: saida ? saida.time_hhmm : "", campo: { tipo: "punch", pIdx, dIdx, idx: 2 * i + 1 } });
    }
    return celulas;
  });

  return { colunas, linhas };
}

function montarLinhasHolerite(value) {
  const paginas = value.pages || [];
  const labels = [];
  const vistos = new Set();
  for (const pagina of paginas) {
    for (const campo of pagina.fields || []) {
      if (!vistos.has(campo.label)) {
        vistos.add(campo.label);
        labels.push(campo.label);
      }
    }
  }

  const colunas = ["Pág.", "Mês", "Ano", ...labels];

  const linhas = paginas.map((pagina, pIdx) => {
    const celulas = [
      { texto: String(pagina.page ?? ""), campo: { tipo: "page", pIdx } },
      { texto: pagina.month || "", campo: { tipo: "month", pIdx } },
      { texto: pagina.year || "", campo: { tipo: "year", pIdx } },
    ];
    for (const label of labels) {
      const campoObj = (pagina.fields || []).find((f) => f.label === label);
      celulas.push({
        texto: campoObj ? campoObj.value : "",
        campo: { tipo: "field-value", pIdx, label },
      });
    }
    return celulas;
  });

  return { colunas, linhas };
}

function aplicarEdicao(campo, novoTexto) {
  estado.sujo = true;
  atualizarStatusSalvar();

  const pages = estado.value.pages;
  if (campo.tipo === "date_raw") {
    pages[campo.pIdx].days[campo.dIdx].date_raw = novoTexto;
  } else if (campo.tipo === "punch") {
    const dia = pages[campo.pIdx].days[campo.dIdx];
    dia.punches = dia.punches || [];
    while (dia.punches.length <= campo.idx) {
      const kind = dia.punches.length % 2 === 0 ? "IN" : "OUT";
      dia.punches.push({ kind, time_raw: "", time_hhmm: "" });
    }
    dia.punches[campo.idx].time_hhmm = novoTexto;
    dia.punches[campo.idx].time_raw = novoTexto;
  } else if (campo.tipo === "page") {
    pages[campo.pIdx].page = Number.parseInt(novoTexto, 10) || novoTexto;
  } else if (campo.tipo === "month") {
    pages[campo.pIdx].month = novoTexto;
  } else if (campo.tipo === "year") {
    pages[campo.pIdx].year = novoTexto;
  } else if (campo.tipo === "field-value") {
    const pagina = pages[campo.pIdx];
    pagina.fields = pagina.fields || [];
    let alvo = pagina.fields.find((f) => f.label === campo.label);
    if (!alvo) {
      alvo = { code: "", label: campo.label, reference: "", value: "" };
      pagina.fields.push(alvo);
    }
    alvo.value = novoTexto;
  }
}

function renderizarTabela() {
  const montador = estado.tipo === "cartao-ponto" ? montarLinhasCartao : montarLinhasHolerite;
  const { colunas, linhas } = montador(estado.value);
  const avisos = estado.avisosPorLinha || [];

  const thead = document.createElement("thead");
  const trCab = document.createElement("tr");
  for (const col of colunas) {
    const th = document.createElement("th");
    th.textContent = col;
    trCab.appendChild(th);
  }
  thead.appendChild(trCab);

  const tbody = document.createElement("tbody");
  const motivosVistos = [];

  linhas.forEach((celulas, i) => {
    const avisosLinha = avisos[i] || [];
    const cor = corDaLinha(avisosLinha);

    const tr = document.createElement("tr");
    if (cor) tr.className = cor;

    for (const celula of celulas) {
      const td = document.createElement("td");
      td.textContent = celula.texto;
      td.contentEditable = "true";
      td.addEventListener("input", () => aplicarEdicao(celula.campo, td.textContent));
      tr.appendChild(td);
    }
    tbody.appendChild(tr);

    if (avisosLinha.length > 0) {
      const textos = avisosLinha.map((codigo) => MOTIVOS_AVISO[codigo] || codigo);
      motivosVistos.push({ linha: i + 1, textos });
    }
  });

  els.tabelaRevisao.innerHTML = "";
  els.tabelaRevisao.appendChild(thead);
  els.tabelaRevisao.appendChild(tbody);

  els.motivosAviso.innerHTML = "";
  for (const { linha, textos } of motivosVistos) {
    const p = document.createElement("p");
    p.className = "motivo-aviso";
    p.textContent = `Linha ${linha}: ${textos.join(" · ")}`;
    els.motivosAviso.appendChild(p);
  }
}

function abrirRevisao(corpo) {
  estado.value = corpo.value;
  estado.avisosPorLinha = corpo.avisos || [];
  estado.sujo = false;

  els.embedPdf.src = `/api/transcricoes/${estado.id}/arquivo`;
  renderizarTabela();
  atualizarStatusSalvar();
  mostrarPainel(els.painelRevisao);
}

function atualizarStatusSalvar() {
  els.statusSalvar.textContent = estado.sujo ? "Há edições não salvas." : "Tudo salvo.";
}

async function salvarCorrecoes() {
  els.btnSalvar.disabled = true;
  try {
    const resp = await fetch(`/api/transcricoes/${estado.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value: estado.value }),
    });
    if (!resp.ok) {
      const corpo = await resp.json().catch(() => ({}));
      alert(corpo.detail || "Não foi possível salvar as correções.");
      return false;
    }
    const atualizado = await fetch(`/api/transcricoes/${estado.id}`).then((r) => r.json());
    estado.value = atualizado.value;
    estado.avisosPorLinha = atualizado.avisos || [];
    estado.sujo = false;
    renderizarTabela();
    atualizarStatusSalvar();
    return true;
  } catch (e) {
    alert("Falha de rede ao salvar as correções.");
    return false;
  } finally {
    els.btnSalvar.disabled = false;
  }
}

async function baixarPlanilha(formato) {
  if (estado.sujo) {
    const ok = await salvarCorrecoes();
    if (!ok) return;
  }
  window.location.href = `/api/transcricoes/${estado.id}/planilha?formato=${formato}`;
}

els.formUpload.addEventListener("submit", enviarUpload);
els.btnTentarOutro.addEventListener("click", voltarParaUpload);
els.btnSalvar.addEventListener("click", salvarCorrecoes);
els.botoesDownload.forEach((botao) => {
  botao.addEventListener("click", () => baixarPlanilha(botao.dataset.formato));
});
