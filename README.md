# MedGuide

Monitoramento e versionamento de diretrizes médicas oficiais. O frontend React/Vite
existente foi preservado. O backend de ingestão usa Python 3.12, FastAPI, PostgreSQL,
Celery/Redis e PyMuPDF. Esta entrega não inclui contas de usuários, IA ou feed.

## Executar

Copie `.env.example` para `.env` e configure `MEDGUIDE_ADMIN_TOKEN`. Para produção,
troque a senha PostgreSQL, atualize a URL do banco e defina uma imagem versionada.

```sh
docker compose -f compose.yaml -f compose.dev.yaml up --build -d
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
docker compose logs -f worker-ingestion
```

O job `migrate` aplica Alembic antes de API/workers. Migrações explícitas e produção:

```sh
docker compose run --rm migrate
docker compose -f compose.yaml -f compose.prod.yaml up --build -d
```

A API escuta em `127.0.0.1:8000`; PostgreSQL/Redis não publicam portas. Produção
precisa de proxy/TLS para acesso externo. Execute apenas uma instância de Beat.
Volumes: `postgres_data`, `redis_data` e `raw_documents`. Produção não monta código.

## Cadastrar a CONITEC

Nenhuma fonte é ativada automaticamente. Após cadastrar, o scheduler verifica o
catálogo diariamente e o conteúdo de cada documento a cada 30 dias, por padrão.
Exemplos em shell POSIX:

```sh
export MEDGUIDE_ADMIN_TOKEN='token-configurado-no-env'
curl -X POST http://127.0.0.1:8000/api/sources \
  -H "Authorization: Bearer $MEDGUIDE_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"code":"conitec_pcdt","connector_key":"conitec_pcdt"}'
curl -X POST http://127.0.0.1:8000/api/sources/ID_DA_FONTE/discover \
  -H "Authorization: Bearer $MEDGUIDE_ADMIN_TOKEN"
```

Coleta retorna 202 com ID durável. `published: false` indica publicação adiada para
o reconciliador, mantendo o registro no banco. Scraping sempre ocorre nos workers.
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
teste, pois suas filas são limpas. A CI configura ambos e valida migração/rollback.

`smoke_http.py` testa a API já iniciada, cadastra uma fonte desabilitada e lê token
de `.env` ou ambiente. `smoke_live.py` consulta o catálogo e baixa apenas um PDF,
validando RAW, extração, persistência e entrega duplicada em banco temporário.
Relatórios ficam em `test-results/`, ignorado no Git.

Frontend: `npm ci`, `npm run dev`, `npm run build`, `npm run lint`.

## Adicionar fonte

1. Implemente `scrapers/<fonte>/` com `discover()` e `fetch_documents()`.
2. Retorne contratos validados, com `external_key`/`reference_key` estáveis.
   Defina schema do `source_context`, sem credenciais. Bytes ficam apenas no worker.
3. Homologue hosts exatos, robots, termos e navegação; use o HTTP restrito e
   registre a factory em `SCRAPER_REGISTRY`. Scrapers não escrevem SQL.
4. Inclua a URL homologada na criação administrativa. Hoje só CONITEC é aceita;
   a API não recebe URLs livres nem imports arbitrários.
5. Adicione fixtures e contratos. `tests/contract/test_multistep.py` demonstra
   detalhe → intermediário → PDF sem alterar detector/versionador.

## Operação

Logs JSON incluem IDs, estágio, duração e resultado. Acompanhe falhas, revisão,
backlog e mudanças de contagem do catálogo. Jobs PENDING e leases expirados são
reconciliados; falhas definitivas exigem retry explícito. Redis não guarda histórico.

Faça backup coordenado de PostgreSQL e RAW antes de atualizar. Valide restauração
separadamente, confira hashes e execute smoke HTTP. Rollback de imagem exige schema
compatível; downgrades que removem tabelas são destrutivos. Não use `down --volumes`
em ambientes com dados a preservar. A CI usa volumes descartáveis.

Detalhes: [arquitetura](docs/architecture.md), [Draw.io](docs/architecture.drawio),
[decisões](docs/decisions/) e [validação](docs/validation.md).
A especificação de referência foi copiada para `docs/` e está no `.gitignore`.
