# SOLUCAO.md

## Como rodar

```bash
cp .env.example .env      # ajuste se quiser; os defaults já funcionam
docker compose up --build
```

Abre em `http://localhost:8000`. `docker compose up` é o requisito duro — validado do zero (`docker compose build --no-cache` + `up`, sem depender de cache de camada) antes desta entrega.

**URL publicada:** `TODO — preencher após o deploy no Render` (ver `docs/dia-6.md`, Bloco 3; blueprint pronto em `render.yaml`).

### Rodar os testes

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest app/tests -q
```

89 testes, todos verdes. Rodam sem Tesseract instalado, com uma exceção: os testes que exercitam OCR de verdade (holerite/cartão escaneados) precisam do binário `tesseract` no PATH — dentro do container ele já vem pelo `Dockerfile` (`apt-get install tesseract-ocr tesseract-ocr-por`); fora do container, só rodam os que usam PDF digital. Rodei a suite completa nos dois ambientes antes de fechar cada dia (local sem OCR, container com OCR) — o `PROCESSO.md` documenta os casos em que os dois divergiram.

## Stack e por quê

Python + FastAPI (API assíncrona, `BackgroundTasks` pro processamento não bloquear o request). `pdfplumber` pra camada digital (dá posição x/y por palavra, essencial pra classificar coluna por proximidade ao cabeçalho em vez de índice fixo). `pytesseract` (Tesseract) pra OCR — escolha explicitamente pedida no enunciado, e a justificativa é dupla: roda local, sem custo por página e sem limite de cota (documentos reais chegam a mais de cem páginas); e não envia documento trabalhista de terceiro pra um serviço de nuvem, o que é também argumento de privacidade, não só de custo. `openpyxl` pros exports `.xlsx` com cor/borda condicional. `SQLite` como armazenamento — volume único, sem concorrência de escrita séria pro tamanho deste desafio, zero infra extra pra subir.

## Arquitetura em 5 linhas

Um pipeline, dois extratores: `POST` grava o PDF e enfileira via `BackgroundTasks`; o mesmo `pipeline.processar()` chama `CartaoPontoExtractor` ou `HoleriteExtractor` conforme o `tipo`, os dois emergindo de `reader.ler()` (detecção digital/OCR por densidade de texto) → `tokens` (parsing de horário/dinheiro/data por regex e semântica) → gramática de cada extractor (classificação de coluna por proximidade ao cabeçalho, nunca por posição fixa) → uma validação de honestidade por cima (nunca inventa, marca `?`). MVC simples: `controllers/` só orquestra HTTP, `models/repository.py` é a única peça que toca SQLite, `services/` tem toda a lógica de domínio e não sabe que FastAPI existe. A extração é dirigida por ESTRUTURA (onde está o cabeçalho, quais colunas ele declara) e não por layout conhecido de antemão — é por isso que o mesmo código lê `time-card-01` e `time-card-02`, que têm cabeçalhos com colunas diferentes, sem `if` por arquivo.

## Decisões técnicas

- **Digital vs. OCR**: cada página decide sozinha, por densidade de caracteres extraídos via `pdfplumber` (`DENSIDADE_MINIMA_CHARS = 200`); abaixo disso, a página passa por OCR. Por página, não por documento — um PDF pode ter páginas digitais e escaneadas misturadas.
- **`?` por confiança de OCR**: Tesseract só dá confiança por PALAVRA (não por caractere); abaixo de `OCR_CONF_THRESHOLD` (65, calibrado contra os 3 exemplos escaneados que tenho), a palavra inteira vira incerta (`"??:??"` em horário; caractere a caractere onde a granularidade permite, como em dinheiro). Documento em `PROCESSO.md` como aproximação, não medição perfeita.
- **Avisos derivados, nunca persistidos**: `calcular_avisos_cartao`/`calcular_avisos_holerite` (`services/tabela.py`) recalculam a cada resposta a partir do `value` atual — corrigir um dado faz o aviso sumir sozinho, sem sincronizar dois lugares.
- **Dinheiro como string, formato brasileiro**: nunca vira `float`. `"2.389,77"` fica exatamente assim; converter perderia o formato original e abriria risco de arredondamento.
- **Ordem do documento preservada**: `days`/`fields`/`pages` nunca são ordenados por data ou competência — é o que permite os avisos de "fora de sequência" significarem alguma coisa.
- **Separador do CSV**: `;` (padrão BR, abre direto no Excel PT-BR) com BOM (`utf-8-sig`) pra acentuação sobreviver ao Excel no Windows.
- **Limite de concorrência de OCR**: `threading.Semaphore` (não `asyncio.Semaphore`) porque `BackgroundTasks` roda `reader.ler()` de forma síncrona num threadpool — um semáforo de asyncio não protegeria nada nesse contexto.
- **Retenção com enforcement real, não só declarado**: ver seção própria abaixo.

## O que ficou de fora e por quê

- **`payroll-01.pdf` (ficha financeira) não é lido.** Layout de 3 mini-tabelas lado a lado, título estilizado sem cabeçalho-âncora reconhecível e sem pares `Rótulo: Valor` — a gramática atual assume um bloco de colunas por página, e esse documento não tem isso. Levanta `LayoutDesconhecidoError` (`status: "erro"`, mensagem legível) em vez de inventar uma leitura. Precisaria de uma técnica genuinamente diferente (zonas por posição x dentro de cada bloco); decidi não implementar às pressas.
- **`time-card-04.pdf` não deveria estar marcado como lido, e hoje está.** É a lacuna mais séria da entrega: esse layout (estrutura por quinzena, sem cabeçalho `Dia | Entrada | Saída` reconhecível) cai no caminho de fallback e produz `status: "concluido"` com "dias" que são na verdade fragmentos de cabeçalho (`"1.QUINZENA"`, números soltos), não batidas de verdade. Devia levantar `LayoutDesconhecidoError`, como `payroll-01.pdf`. Não corrigido — precisaria de um piso mínimo de sinal (dias com batida real por página) abaixo do qual o fallback desiste, calibrado contra mais de um exemplo desse layout, e não quis decidir esse piso às pressas com uma amostra de um documento só.
- **Qual tipo ficou mais fraco**: cartão de ponto está mais maduro que holerite. Os dois têm um documento não suportado (`payroll-01`/`time-card-04`), mas o cartão de ponto tem calibração de OCR medida (binarização testada e descartada com dado, limiar de confiança justificado) e uma bateria maior de casos sintéticos (faixa colada, confiança baixa, ordem fora de sequência, área de totais). O holerite tem uma lacuna mais séria de honestidade: **a extração de holerite não marca `?` por incerteza de OCR** — `tokens.normalizar_dinheiro` e a montagem de rótulo em `extractors/holerite.py` nunca olham `Palavra.confianca`, diferente do cartão de ponto. Num holerite escaneado (`payroll-04.pdf`), um dígito mal lido pelo Tesseract passa direto como se fosse certo, em vez de virar `?`. Achei isso girando o Bloco 2 de hoje (configuração), não corrigi — é trabalho de calibração do tamanho do que os Dias 3/4 fizeram pro cartão de ponto, não cabia no orçamento de hoje. É a maior dívida de honestidade em aberto nesta entrega.
- **Mini-tabela de bases-resumo do `payroll-04.pdf`** (Salário Base / Base INSS / Base FGTS / FGTS Mês / Base IRRF, rótulos numa linha e valores na linha de baixo) não é seguida — a gramática espera rótulo e valor na mesma linha. Descartada explicitamente (rótulo puramente numérico nunca vira `field`), não inventada errado, mas a informação desses 5 campos não sobra em lugar nenhum da saída.
- **Herança de cabeçalho entre páginas do cartão de ponto** processa a página inteira quando ela não repete cabeçalho próprio, em vez de cortar acima de onde o cabeçalho ficaria. Não aparece em nenhum exemplo atual (todos repetem cabeçalho), mas está exposto.
- **Bônus**: nenhum implementado (rastreabilidade visual, detecção automática de tipo, ficha financeira anual, layout desconhecido além do que já existe). Priorizei o ciclo completo com os dois tipos parcialmente lidos em vez de gastar tempo em bônus com um tipo incompleto.

## Testes: por que esses

- **Tokens** (`test_tokens.py`, `test_reader.py`): unidade, casos sujos sintéticos — normalização de horário/data/dinheiro/competência com entrada malformada, sem depender de nenhum PDF.
- **Gramática dos extractors** (`test_extractor_cartao_ponto.py`, `test_extractor_holerite.py`): uma fixture por regra achada calibrando contra documento real (faixa colada, confiança baixa, área de totais, transbordo de coluna, verbas lado a lado) — cada teste existe porque um bug real motivou ele, não por cobertura abstrata.
- **Transposição da planilha** (`test_tabela.py`, `test_exporters.py`): `value` → `{colunas, linhas}` e avisos/cores, incluindo "vermelho ganha" quando os dois disparam na mesma linha.
- **Contrato HTTP** (`test_contract.py`): os 5 endpoints, status codes, ciclo assíncrono completo (`processando` → `concluido` sem bloquear o request), limpeza de retenção.
- **Os 8 exemplos como regressão, não como unidade**: rodados manualmente (curl + container real) a cada dia de calibração, contando avisos e batidas por arquivo antes de aceitar uma mudança como pronta — é assim que os falsos positivos de "mês não sequencial"/"data não sequencial" e o bug das batidas inventadas nas colunas de totais foram achados, nenhum deles apareceu num teste unitário primeiro.

## Política de retenção

Guarda: o PDF original (`UPLOAD_DIR`, disco do container) e a transcrição (`value` + metadados, SQLite em `DB_PATH`). Não guarda: nada além disso — sem PII em log (logs usam só `id`, número de página, timestamps e somas; nunca nome, CPF, matrícula ou valor de verba específica).

Por quanto tempo: `RETENCAO_HORAS` (default 24h, `.env.example`). **Enforcement real, não só declarado**: a cada novo `POST /api/transcricoes`, uma varredura (`_limpar_expirados`, `controllers/transcricao_controller.py`) apaga do SQLite e do disco tudo mais velho que `RETENCAO_HORAS`. É best-effort — dispara só quando alguém envia um documento novo, não é um cron dedicado; um servidor parado sem uploads não limpa sozinho. Documentado assim de propósito, não escondido.

Efeito do free tier do Render (se o deploy usar disco efêmero, sem volume persistente): o disco some a cada redeploy, o que na prática é uma segunda camada de retenção — mais agressiva que `RETENCAO_HORAS`, mas na direção certa (menos dado parado, não mais).

## Segurança

- Limite de tamanho de upload (`MAX_UPLOAD_MB`, default 20MB) — verificado durante o streaming do upload, não só no fim.
- Validação por magic bytes (`%PDF` nos primeiros bytes) — um `.txt` renomeado pra `.pdf` é recusado com `400` antes de qualquer processamento.
- Limite de páginas (`MAX_PAGINAS`, default 50) — recusa documento grande demais antes de decidir a rota digital/OCR de qualquer página, evitando estourar memória com um upload fora do padrão da amostra (documentos reais chegam a 129 páginas).
- Concorrência de OCR limitada (`OCR_MAX_CONCORRENTES`, `threading.Semaphore`) — evita N uploads simultâneos rasterizando páginas ao mesmo tempo e estourando RAM.
- Nenhum segredo no repositório — `.env` no `.gitignore` desde o commit inicial, `.env.example` versionado como documentação, conferido contra todo o histórico de commits (`git log -p --all`) sem achado.
- Retenção limitada por padrão (ver seção acima) em vez de reter indefinidamente.
