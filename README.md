# MedGuide

Monitoramento e versionamento de diretrizes médicas oficiais. O frontend React/Vite
existente foi preservado. O backend de ingestão usa Python 3.12, FastAPI, PostgreSQL,
Celery/Redis e PyMuPDF. Esta entrega não inclui contas de usuários, IA ou feed.

## Executar localmente

O projeto roda apenas localmente, com um único `compose.yaml`. No Ubuntu, dentro
da pasta do projeto:

```sh
test -f .env || cp .env.example .env
docker compose up --build -d
docker compose exec api python -m medguide sources status conitec_pcdt
```

A CONITEC é cadastrada e habilitada na primeira inicialização. O scheduler inicia
a descoberta no próximo ciclo, normalmente em até um minuto. Cadastros existentes,
desativações e intervalos personalizados são preservados ao reiniciar.

Para conferir a infraestrutura:

```sh
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
docker compose logs -f worker-ingestion
```

O job `migrate` aplica Alembic e cadastra fontes ausentes antes de API/workers/Beat.
Para repetir essa preparação manualmente:

```sh
docker compose run --rm migrate
```

A API escuta em `127.0.0.1:8000`; PostgreSQL/Redis ficam dentro da rede do Compose.
Volumes: `postgres_data`, `redis_data` e `raw_documents`. O código Python é montado
do diretório local e a API recarrega ao editar. Após mudar código dos workers ou
scheduler, execute `docker compose restart worker-discovery worker-ingestion beat`.
Alterações nas dependências exigem `docker compose up --build -d`.

Para parar: `docker compose down`. Os volumes e documentos são preservados.
Os serviços são iniciados manualmente; não há pipeline nem provisionamento de ambientes.

## Operar fontes pelo nome

O código `conitec_pcdt` identifica a CONITEC. O catálogo é verificado diariamente e
o conteúdo de cada documento a cada 30 dias, por padrão. Os comandos locais usam
as configurações do container e dispensam token, UUID e requisições HTTP:

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

Para usar a API ou `scripts/smoke_http.py`, configure `MEDGUIDE_ADMIN_TOKEN` no `.env`
e recrie os serviços com `docker compose up -d`. Os comandos locais não exigem esse token.
Pedidos HTTP de coleta retornam 202 com ID durável. `published: false` indica envio
adiado para o reconciliador, mantendo o registro no banco.
PATCH `/api/sources/{id}` configura `enabled`, `discovery_interval` e
`content_recheck_interval` em segundos (mínimo 60).

Todas as rotas `/api` exigem token Bearer. Sem token configurado, fecham o acesso.
OpenAPI em `/docs`. Listagens aceitam `limit` (1–200) e `offset`.

| Rota | Finalidade |
|---|---|
| `GET /api/sources` | Fontes e configuração |
| `GET /api/runs` e `/api/runs/{id}` | Execuções, contagens e falhas |
| `GET /api/guidelines` e `/api/guidelines/{id}` | Diretrizes e versão corrente |
| `GET /api/guidelines/{id}/observations` | Metadados observados |
| `GET /api/guidelines/{id}/versions` | Histórico de conteúdo |
| `GET /api/guidelines/{id}/artifacts` | Arquivos, hashes e páginas |
| `GET /api/artifacts/{id}/raw` | Original com integridade verificada |
| `GET /api/jobs` e `/api/jobs/{id}` | Estado, tentativas, estágio e erro |
| `POST /api/jobs/{id}/retry` | Novo job para falha/revisão, preservando o anterior |
| `GET /api/metrics` | Backlog, falhas e último sucesso |

Originais ficam restritos à administração. `NEEDS_REVIEW` sinaliza documento sem
texto extraível ou indisponível. OCR não está habilitado. Mudanças apenas em
metadados ou bytes não criam versões textuais falsas.

## Desenvolvimento e testes

```sh
uv sync --frozen
uv run ruff check src/medguide tests scripts migrations
uv run ruff format --check src/medguide tests scripts migrations
uv run mypy src/medguide
uv run pytest
uv run python scripts/smoke_http.py
uv run python scripts/smoke_live.py
```

Os testes rápidos usam SQLite temporário. `TEST_DATABASE_URL` habilita testes em
PostgreSQL e deve apontar para banco **descartável**: fixtures criam/removem tabelas.
`TEST_REDIS_URL` habilita entrega Celery real e deve usar banco Redis exclusivo de
teste, pois suas filas são limpas. Esses testes são executados manualmente quando
as respectivas variáveis estão configuradas; não há workflow de CI.

`smoke_http.py` testa a API já iniciada, cadastra uma fonte desabilitada e lê token
de `.env` ou ambiente. `smoke_live.py` consulta o catálogo e baixa apenas um PDF,
validando RAW, extração, persistência e entrega duplicada em banco temporário.
Relatórios ficam em `test-results/`, ignorado no Git.

Para auditar os documentos já coletados no ambiente local:

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

Frontend: `npm ci`, `npm run dev`, `npm run build`, `npm run lint`.

## Adicionar fonte

1. Implemente `scrapers/<fonte>/` com `discover()` e `fetch_documents()`.
2. Retorne contratos validados, com `external_key`/`reference_key` estáveis.
   Defina schema do `source_context`, sem credenciais. Bytes ficam apenas no worker.
3. Homologue hosts exatos, robots, termos e navegação; use o HTTP restrito e
   adicione uma `SourceDefinition` em `SOURCE_DEFINITIONS`, com código, nome, URL,
   factory e habilitação inicial. O `SCRAPER_REGISTRY` é derivado dessas definições.
   Scrapers não escrevem SQL.
4. Execute `docker compose run --rm migrate`: a fonte ausente será cadastrada
   com os intervalos do `.env`. A API usa a mesma definição aprovada de URL/conector;
   não recebe URLs livres nem imports arbitrários.
5. Adicione fixtures e contratos. `tests/contract/test_multistep.py` demonstra
   detalhe → intermediário → PDF sem alterar detector/versionador.

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
