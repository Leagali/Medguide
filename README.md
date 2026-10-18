# MedGuide

Monitoramento e versionamento de diretrizes médicas oficiais. O backend usa Python
3.12, FastAPI, PostgreSQL, Celery/Redis e PyMuPDF. O conector implementado é o catálogo
de Protocolos Clínicos e Diretrizes Terapêuticas (PCDT) da CONITEC: descobre entradas,
baixa documentos, extrai texto por página e mantém originais e versões observadas.

O frontend React/Vite é uma tela visual de login, sem integração com a API. A leitura
dos documentos coletados está disponível pela API e pelas exportações descritas
abaixo. Contas de usuários, tela de leitura, IA e feed ainda não estão implementados.

## Roteiro de demonstração para o professor

Siga os passos na ordem. Os comandos de terminal abaixo usam **Ubuntu ou Ubuntu/WSL
(Bash)**, dentro da pasta do projeto. Os blocos `sql` e os comandos iniciados por `\`
são executados dentro do `psql`, aberto no passo 4. Não é necessário instalar um
cliente PostgreSQL no host nem publicar a porta do banco.

### 1. Iniciar os serviços e verificar a API

```sh
test -f .env || cp .env.example .env
docker compose up --build -d
docker compose ps -a
```

Espere a API ficar `healthy`. O serviço `migrate` deve terminar com `Exited (0)`;
PostgreSQL, Redis, API, Beat e os dois workers devem permanecer em execução.
Depois, verifique os endpoints, que devem retornar `{"status":"ok"}` e
`{"status":"ready"}`:

```sh
curl --fail http://127.0.0.1:8000/healthz
curl --fail http://127.0.0.1:8000/readyz
```

### 2. Solicitar a coleta e acompanhar o processamento

```sh
docker compose exec api python -m medguide sources list
docker compose exec api python -m medguide sources enable conitec_pcdt
docker compose exec api python -m medguide sources run conitec_pcdt
docker compose exec api python -m medguide sources status conitec_pcdt
docker compose logs --tail 30 worker-discovery worker-ingestion
```

O bootstrap já cadastra a CONITEC e o Beat também pode iniciar a descoberta.
O comando `run` solicita a execução imediatamente e reutiliza uma descoberta ativa.
Repita `sources status conitec_pcdt` até a descoberta terminar e os jobs pendentes/em
processamento concluírem. Se houver falhas ou revisão, consulte seus erros antes da
apresentação. A primeira coleta pode demorar; prepare os dados antes da aula.

Explique o fluxo: **Beat/CLI → descoberta → jobs no PostgreSQL → filas Redis/Celery
→ download nos workers → original em volume Docker → texto e versões no PostgreSQL**.
Repetir a descoberta sem alterações e antes do prazo de reverificação pode encontrar
as mesmas diretrizes e criar zero novos jobs; isso é esperado.

### 3. Mostrar a documentação e os dados pela API

Abra [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Clique em **Authorize**
e informe o valor de `MEDGUIDE_ADMIN_TOKEN` do `.env`, sem o prefixo `Bearer`.
Execute, nesta ordem:

1. `GET /api/sources`: configuração da fonte.
2. `GET /api/runs`: resultado das descobertas.
3. `GET /api/jobs`: processamento dos documentos.
4. `GET /api/guidelines`: copie um `id` e seu `current_version_id`.
5. `GET /api/guidelines/{id}/versions`: texto completo em `extracted_text`.
6. `GET /api/guidelines/{id}/artifacts`: páginas, hashes e IDs dos originais.
7. `GET /api/artifacts/{id}/raw`: use o ID do **artefato** para baixar o original;
   se for PDF, salve com extensão `.pdf`.

### 4. Entrar no PostgreSQL pelo container

No terminal Ubuntu, execute:

```sh
docker compose exec postgres sh -c 'exec psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

As variáveis são lidas dentro do container. No prompt do `psql`, execute:

```sql
\pset pager off
\dt
SET default_transaction_read_only = on;
```

`\dt` lista as tabelas. A sessão fica configurada para consultas de leitura.
Mantenha esse terminal aberto para os passos 5 a 7; finalize cada query com `;`.

### 5. Conferir cadastro, execução e persistência

Primeiro, mostre a fonte e seus intervalos (em segundos):

```sql
SELECT code, enabled, discovery_interval, content_recheck_interval, next_due_at
FROM sources
ORDER BY code;
```

Confira quantos registros foram persistidos, sem multiplicar linhas com joins:

```sql
SELECT
    (SELECT count(*) FROM sources) AS fontes,
    (SELECT count(*) FROM guidelines) AS diretrizes,
    (SELECT count(*) FROM artifacts) AS originais,
    (SELECT count(*) FROM guideline_versions) AS versoes_textuais,
    (SELECT count(*) FROM ingestion_jobs) AS jobs;
```

Mostre os jobs por estado e as últimas descobertas da CONITEC:

```sql
SELECT status, count(*) AS quantidade
FROM ingestion_jobs
GROUP BY status
ORDER BY status;

SELECT r.id, r.status, r.found_count, r.queued_count, r.attempt_count,
       r.started_at, r.finished_at, r.error_summary
FROM collection_runs AS r
JOIN sources AS s ON s.id = r.source_id
WHERE s.code = 'conitec_pcdt'
ORDER BY r.started_at DESC
LIMIT 5;
```

`found_count` é a quantidade descoberta no catálogo; `queued_count` é a quantidade
de jobs criada naquela descoberta. Uma descoberta concluída não significa que os
jobs de ingestão também terminaram. As contagens dependem do catálogo e do histórico
local; os 132 documentos da validação anterior não são um valor fixo do sistema.

Liste diretrizes com sua versão corrente e o tamanho do texto salvo:

```sql
SELECT g.id, g.title, v.id AS version_id, v.observed_version,
       char_length(v.extracted_text) AS caracteres, v.detected_at
FROM guidelines AS g
LEFT JOIN guideline_versions AS v ON v.id = g.current_version_id
ORDER BY g.title
LIMIT 10;
```

O `LEFT JOIN` também mostra diretrizes descobertas que ainda não têm uma versão.
`observed_version` é a sequência de versões detectadas pelo coletor, não a edição
oficial publicada pela CONITEC.

### 6. Ler o texto da Asma e consultar seu histórico

Use Asma como exemplo. Se ela ainda não tiver sido extraída, aguarde os jobs ou
substitua o filtro de título por outra diretriz que já tenha versão corrente.

```sql
SELECT g.title, v.observed_version,
       char_length(v.extracted_text) AS caracteres,
       left(v.extracted_text, 2000) AS inicio_do_texto
FROM guidelines AS g
JOIN guideline_versions AS v ON v.id = g.current_version_id
WHERE g.title ILIKE '%asma%'
ORDER BY g.title
LIMIT 1;
```

Mostre também a sexta página extraída, para ler uma parte interna do documento:

```sql
SELECT g.title, a.pages_json -> 5 ->> 'page_number' AS pagina,
       left(a.pages_json -> 5 ->> 'text', 2000) AS texto_da_pagina
FROM guidelines AS g
JOIN version_artifacts AS va ON va.version_id = g.current_version_id
JOIN artifacts AS a ON a.id = va.artifact_id
WHERE g.title ILIKE '%asma%'
ORDER BY g.title, a.reference_key
LIMIT 1;
```

O índice do array começa em zero: `-> 5` acessa a sexta página. Os trechos são
limitados apenas para caber na apresentação; o texto completo permanece no banco.
Consulte as versões e os hashes de conteúdo observados:

```sql
SELECT g.title, v.observed_version, v.detected_at,
       char_length(v.extracted_text) AS caracteres, v.composite_content_sha256
FROM guidelines AS g
JOIN guideline_versions AS v ON v.guideline_id = g.id
WHERE g.title ILIKE '%asma%'
ORDER BY g.title, v.observed_version DESC;
```

É normal existir apenas uma versão se o coletor ainda não observou mudanças.

### 7. Relacionar a versão ao PDF original e verificar erros

```sql
SELECT g.title, a.id AS artifact_id, a.source_url, a.media_type,
       a.size_bytes, json_array_length(a.pages_json) AS paginas,
       a.extraction_status, a.raw_sha256, a.content_sha256,
       '/data/raw/' || a.storage_key AS caminho_no_container
FROM guidelines AS g
JOIN version_artifacts AS va ON va.version_id = g.current_version_id
JOIN artifacts AS a ON a.id = va.artifact_id
WHERE g.title ILIKE '%asma%'
ORDER BY g.title, a.reference_key;

SELECT g.title, j.id AS job_id, j.status, j.stage, j.attempt_count, j.last_error
FROM ingestion_jobs AS j
JOIN guidelines AS g ON g.id = j.guideline_id
WHERE j.status IN ('FAILED', 'NEEDS_REVIEW')
ORDER BY j.created_at DESC
LIMIT 10;
```

O hash RAW identifica os bytes do original; o hash de conteúdo identifica o texto
normalizado por página. A versão reúne os hashes dos documentos vinculados.
Se a consulta de erros retornar zero linhas, não há jobs nesses estados.
O caminho `/data/raw/...` fica no container, dentro do volume Docker.

Saia do `psql` antes de voltar aos comandos de terminal:

```sql
\q
```

### 8. Exportar e abrir o texto completo em um arquivo local

No terminal Ubuntu, exporte a versão corrente da Asma. O comando abaixo usa as
opções do `psql` para gravar o texto com suas quebras de linha, sem cabeçalhos:

```sh
mkdir -p test-results
docker compose exec -T postgres sh -c \
  'exec psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -A -t -v ON_ERROR_STOP=1' \
  > test-results/asma.txt <<'SQL'
SELECT v.extracted_text
FROM guidelines AS g
JOIN guideline_versions AS v ON v.id = g.current_version_id
WHERE g.title ILIKE '%asma%'
ORDER BY g.title
LIMIT 1;
SQL
less test-results/asma.txt
```

Use `q` para sair do `less`. O arquivo fica em `test-results/asma.txt`, na pasta
local do projeto, e é ignorado pelo Git. Se não houver versão para o filtro,
o arquivo estará vazio; confira o passo 6. As consultas não alteram os dados coletados.

Para uma comprovação adicional de integridade, execute a auditoria de originais,
textos e API em [Desenvolvimento e testes](#desenvolvimento-e-testes). Para mostrar
a página visual do frontend, siga [Frontend visual](#frontend-visual); ela não lê
esses documentos. Ao terminar a demonstração, `docker compose down` para os serviços
e preserva os volumes com as coletas.

## Executar localmente

O projeto roda apenas localmente, com um único `compose.yaml`. Para o backend,
é necessário Docker com o plugin Docker Compose e suporte a containers Linux.
Python, PostgreSQL e Redis são executados nos containers; não precisam estar
instalados no Ubuntu. Na pasta do projeto, pelo terminal Ubuntu ou Ubuntu/WSL:

```sh
test -f .env || cp .env.example .env
docker compose up --build -d
docker compose exec api python -m medguide sources status conitec_pcdt
```

A CONITEC é cadastrada e habilitada na primeira inicialização. O Beat verifica
fontes vencidas a cada minuto e publica a descoberta para o worker. A coleta completa
continua em segundo plano e depende da fila e do acesso à fonte oficial. Cadastros
existentes, desativações e intervalos personalizados são preservados ao reiniciar.

Para conferir a infraestrutura:

```sh
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
docker compose ps -a
docker compose logs -f worker-ingestion
```

`/healthz` verifica se a API responde. `/readyz` também verifica banco, schema,
Redis e escrita no armazenamento; não confirma que os workers estão processando.
O container `migrate` terminar com `Exited (0)` é esperado.

O job `migrate` aplica Alembic e cadastra fontes ausentes antes de API/workers/Beat.
Para repetir essa preparação manualmente:

```sh
docker compose run --rm migrate
```

A API escuta em `127.0.0.1:8000`; PostgreSQL/Redis ficam dentro da rede do Compose.
Volumes: `postgres_data`, `redis_data` e `raw_documents`. O código Python é montado
do diretório local e a API recarrega ao editar. Após mudar código dos workers ou
scheduler, execute `docker compose restart worker-discovery worker-ingestion beat`.
Alterações nas dependências ou nos arquivos de migração exigem reconstruir a imagem
com `docker compose up --build -d`, pois as migrações não são montadas do host.
Após alterar o `.env`, use `docker compose up -d` para recriar os serviços afetados;
apenas `restart` não atualiza suas variáveis de ambiente.

Para parar: `docker compose down`. Os volumes e documentos são preservados.
Os serviços são iniciados manualmente; não há pipeline nem provisionamento de ambientes.

## Operar fontes pelo código

O código `conitec_pcdt` identifica a CONITEC. Por padrão, o catálogo tem intervalo
de descoberta de um dia. Documentos com metadados estáveis ficam elegíveis para
nova verificação de conteúdo após 30 dias; mudanças detectadas no catálogo também
podem gerar jobs de ingestão. Os comandos locais usam as configurações do container
e dispensam token, UUID e requisições HTTP:

```sh
docker compose exec api python -m medguide sources list
docker compose exec api python -m medguide sources run conitec_pcdt
docker compose exec api python -m medguide sources status conitec_pcdt
docker compose exec api python -m medguide sources disable conitec_pcdt
docker compose exec api python -m medguide sources enable conitec_pcdt
```

`run` salva o pedido e enfileira a descoberta; o download/extração ocorre nos workers.
Se já houver uma descoberta ativa, informa e reutiliza essa execução. Fonte
desabilitada precisa de `enable` antes de executar. Falha no Redis mantém o pedido
salvo e informa que o reconciliador tentará publicá-lo novamente. Mantenha o Beat ativo.
`enable` preserva o agendamento existente; para solicitar uma descoberta agora,
execute `run` depois de habilitar. Alterar intervalos também preserva a próxima
descoberta já agendada. Os valores do `.env` são padrões para novos cadastros;
para mudar fontes existentes, use o PATCH da API.

`status` separa a última descoberta dos totais históricos de jobs daquela fonte.
Uma descoberta COMPLETED pode ter PDFs ainda pendentes. Os totais incluem jobs
anteriores com falha, mesmo após retry manual. O status consulta o banco; não atesta
que Beat e workers estão rodando. Confira processos com `docker compose ps -a`.

Todos os comandos aceitam `--json`, por exemplo `sources status conitec_pcdt --json`.
Para cadastrar fontes padrão ausentes sem coletar, preservando configurações existentes:

```sh
docker compose exec api python -m medguide sources bootstrap
```

## API HTTP

Abra [Swagger UI](http://127.0.0.1:8000/docs) no navegador. O schema JSON está em
[/openapi.json](http://127.0.0.1:8000/openapi.json). Essas páginas são públicas;
para executar as rotas `/api`, clique em **Authorize**, informe apenas o valor de
`MEDGUIDE_ADMIN_TOKEN` do seu `.env` (sem o prefixo `Bearer`) e confirme.

O `.env.example` fornece um token para uso local. Se o seu `.env` não tiver token,
configure-o e recrie os serviços com `docker compose up -d`. O mesmo token é usado
por `scripts/smoke_http.py`; os comandos locais de fontes dispensam autenticação HTTP.
Pedidos HTTP de coleta retornam 202 com ID durável. `published: false` indica envio
adiado para o reconciliador, mantendo o registro no banco.
PATCH `/api/sources/{id}` configura `enabled`, `discovery_interval` e
`content_recheck_interval` em segundos (mínimo 60).

Todas as rotas `/api` exigem token Bearer. Sem token configurado, fecham o acesso.
Listagens aceitam `limit` (1–200, padrão 50) e `offset`.

| Rota | Finalidade |
|---|---|
| `GET /api/sources` | Fontes e configuração |
| `POST /api/sources` | Cadastro com um conector homologado |
| `PATCH /api/sources/{id}` | Habilitação e intervalos da fonte |
| `POST /api/sources/{id}/discover` | Solicitar ou reutilizar uma descoberta ativa |
| `GET /api/runs` e `/api/runs/{id}` | Execuções, contagens e falhas |
| `GET /api/guidelines` e `/api/guidelines/{id}` | Diretrizes e versão corrente |
| `GET /api/guidelines/{id}/observations` | Metadados observados |
| `GET /api/guidelines/{id}/versions` | Histórico e texto completo em `extracted_text` |
| `GET /api/guidelines/{id}/artifacts` | Arquivos, hashes e páginas |
| `GET /api/artifacts/{id}/raw` | Original com integridade verificada |
| `GET /api/jobs` e `/api/jobs/{id}` | Estado, tentativas, estágio e erro |
| `POST /api/jobs/{id}/retry` | Novo job para falha/revisão, preservando o anterior |
| `GET /api/metrics` | Backlog, falhas e último sucesso |

Originais ficam restritos à administração. `NEEDS_REVIEW` sinaliza casos que exigem
revisão, como extração vazia; outras falhas podem terminar em `FAILED`. OCR não está
habilitado. Mudanças apenas em metadados ou bytes não criam versões textuais novas
quando o texto normalizado permanece igual.

Se o navegador não abrir `/docs`, verifique no terminal Ubuntu:

```sh
docker compose ps -a
docker compose logs --tail 80 api migrate
curl --noproxy '*' -v --max-time 10 http://127.0.0.1:8000/docs
```

Se o `curl` retorna 200 no Ubuntu/WSL e o navegador Windows falha, a API está
respondendo no Ubuntu; verifique o acesso do Windows ao localhost do WSL.
O Swagger também precisa de acesso à internet para carregar seus arquivos do CDN.

## Onde ler os textos e os originais

Os textos completos ficam no PostgreSQL, em `guideline_versions.extracted_text`;
o texto por página fica em `artifacts.pages_json`. PDFs originais ficam no volume
Docker `raw_documents`, montado em `/data/raw` nos containers, com nomes derivados
do hash. A coleta não cria automaticamente uma pasta de PDFs ou `.txt` no repositório.

No Swagger, após autorizar:

1. Execute `GET /api/guidelines` e copie o `id` da diretriz desejada. Use `offset`
   para consultar as páginas seguintes. Uma entrada descoberta pode ainda não ter texto.
2. Execute `GET /api/guidelines/{id}/versions` e leia `extracted_text`. Para identificar
   a versão corrente, compare o ID com `current_version_id` da diretriz.
3. Execute `GET /api/guidelines/{id}/artifacts` para consultar páginas e IDs de arquivos.
4. Use o ID do artefato em `GET /api/artifacts/{id}/raw` para baixar o original.
   O download recebe extensão `.raw`; para um artefato PDF, salve-o com extensão `.pdf`.

Para obter amostras em arquivos `.txt` no Ubuntu, execute a auditoria descrita abaixo.
Texto simples pode perder tabelas, sobrescritos e formatação; gráficos permanecem
no PDF original. As versões representam mudanças observadas pelo coletor, sem
reconstruir publicações anteriores ao início do monitoramento.

## Desenvolvimento e testes

Os comandos desta seção são executados no host Ubuntu, na pasta do projeto.
Instale `uv` para preparar o ambiente Python de desenvolvimento:

```sh
uv sync --frozen --python 3.12
uv run ruff check src/medguide tests scripts migrations
uv run ruff format --check src/medguide tests scripts migrations
uv run mypy src/medguide
uv run pytest
```

Os testes rápidos usam SQLite temporário. `TEST_DATABASE_URL` habilita testes em
PostgreSQL e deve apontar para banco **descartável**: fixtures criam/removem tabelas.
`TEST_REDIS_URL` habilita entrega Celery real e deve usar banco Redis exclusivo de
teste, pois suas filas são limpas. Esses testes são executados manualmente quando
as respectivas variáveis estão configuradas; não há workflow de CI.
Os testes que exigem esses serviços são pulados se as variáveis não estiverem
configuradas. Os endereços devem ser acessíveis ao processo de teste: o Compose
não publica portas de PostgreSQL/Redis no host. Não use o banco de coletas nos testes.

Com a API do Compose iniciada e o token configurado no `.env` do host:

```sh
uv run python scripts/smoke_http.py
```

Para uma coleta real limitada, com acesso à internet e sem depender dos containers:

```sh
uv run python scripts/smoke_live.py
```

`smoke_http.py` testa a API já iniciada, cadastra uma fonte desabilitada e lê token
de `.env` ou ambiente. `smoke_live.py` consulta o catálogo e baixa apenas um PDF,
validando RAW, extração, persistência e reexecução do mesmo job em SQLite temporário.
Esse último script chama o serviço diretamente; não valida as filas Celery/Redis.
Relatórios ficam em `test-results/`, ignorado no Git.

Para auditar os documentos já coletados, mantenha a API iniciada e aguarde a extração
terminar. O script exige artefatos com extração concluída e pelo menos uma das amostras
CONITEC: Asma, Diabete Melito Tipo 2, Câncer de Mama ou Acidentes Escorpiônicos.
Execute no host, usando o Python e as dependências do container:

```sh
docker compose exec -T api python - < scripts/validate_core.py
mkdir -p test-results/core-validation
docker compose cp api:/tmp/medguide-core-validation/. ./test-results/core-validation
```

A auditoria confere arquivos originais, hashes, reextração por página, composição
das versões e texto completo. Quando o token HTTP está configurado, também compara
textos e PDFs retornados pela API. Exporta amostras completas em `.txt`, uma página
do PDF original e `report.json`. Não altera os registros nem agenda novas coletas;
reextrair todos os documentos pode levar alguns minutos.

Na validação integrada de 17/10/2026, foram aprovados 58 testes com PostgreSQL e
Redis reais, sem testes pulados, com 90% de cobertura. Também foram auditados
132 originais e 132 versões textuais. São resultados daquela execução; as evidências
e limitações estão em [docs/validation.md](docs/validation.md).

## Frontend visual

O Compose inicia apenas o backend. Para abrir a tela React/Vite, use Node.js
20.19+ da linha 20 ou 22.12+ e npm no host, conforme os requisitos das dependências:

```sh
npm ci
npm run dev
```

Abra o endereço exibido pelo Vite. `npm run build` gera a aplicação em `dist/`;
`npm run lint` executa o Oxlint. A tela não autentica usuários nem exibe as coletas.

## Adicionar fonte

1. Implemente `src/medguide/scrapers/<fonte>/` com `discover()` e `fetch_documents()`.
2. Retorne contratos validados, com `external_key`/`reference_key` estáveis.
   Defina schema do `source_context`, sem credenciais. Bytes ficam apenas no worker.
3. Homologue hosts exatos, robots, termos e navegação; use o HTTP restrito e
   adicione uma `SourceDefinition` em `src/medguide/scrapers/registry.py`
   (`SOURCE_DEFINITIONS`), com código, nome, chave do conector, URL,
   factory e habilitação inicial. O `SCRAPER_REGISTRY` é derivado dessas definições.
   Scrapers não escrevem SQL.
4. Execute `docker compose up --build -d` para atualizar a imagem e aplicar o bootstrap,
   e `docker compose restart worker-discovery worker-ingestion beat` para recarregar
   os processos que já estavam ativos. A fonte ausente será cadastrada com os intervalos
   do `.env`. A API usa a mesma definição aprovada de URL/conector; não recebe URLs
   livres nem imports arbitrários. Para apenas cadastrar uma definição já disponível,
   use `sources bootstrap`; não é necessário implementar outro conector.
5. Adicione fixtures e contratos. `tests/contract/test_multistep.py` demonstra
   detalhe → intermediário → PDF sem alterar detector/versionador.

O conector de múltiplas etapas desse teste é simulado. Atualmente, apenas a CONITEC
tem implementação para coleta oficial. Seu identificador deriva do título clínico;
renomeações podem exigir reconciliação manual. São coletados o documento principal
e anexos explícitos; links separados de portarias/resumos não são versionados à parte.

## Operação

Logs JSON incluem IDs, estágio, duração e resultado. Acompanhe falhas, revisão,
backlog e mudanças de contagem do catálogo. Jobs PENDING e leases expirados são
reconciliados; falhas definitivas exigem retry explícito. Redis não guarda histórico.

Para preservar coletas locais, mantenha os volumes de PostgreSQL e RAW. Não use
`docker compose down --volumes` se quiser manter esses dados. Downgrades Alembic
que removem tabelas devem ser usados somente em bancos descartáveis de teste.

Detalhes: [arquitetura](docs/architecture.md), [Draw.io](docs/architecture.drawio),
[decisões](docs/decisions/) e [validação](docs/validation.md).
A especificação de referência foi copiada para `docs/` e está no `.gitignore`.
