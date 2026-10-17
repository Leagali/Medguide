# Validação da implementação — 17/10/2026

Ambiente local: Windows, Python 3.12.2, PostgreSQL 17.11 temporário escutando
somente em 127.0.0.1. Banco/arquivos de ensaio estão no diretório ignorado `data/`.
Nenhum serviço de banco foi instalado no sistema. Frontend existente preservado.

## Evidências executadas

Resultado final: **47 testes aprovados, 1 pulado por ausência de Redis real**;
cobertura total medida em **87%**. O teste pulado pode ser executado manualmente
configurando TEST_DATABASE_URL e TEST_REDIS_URL para serviços locais de teste.

- Ruff (lint/formatação) e mypy no backend.
- Migrações Alembic até head, detecção de drift e rollback/reaplicação no PostgreSQL.
- Suíte de unidade, contrato, integração e requisições com PostgreSQL real,
  incluindo reserva concorrente de fonte e claim concorrente do mesmo job.
- Testes de alterações de metadados/bytes/texto, reversão, múltiplos anexos,
  extração vazia, falha isolada, lease expirado, retries e Retry-After durável.
- `npm run build` e `npm run lint` aprovados.
- Requisições por socket a Uvicorn em 127.0.0.1:8765: health 200; leitura 200;
  cadastro 201; token incorreto 401; conflito/desativação 409; schema inválido 422.
- Readiness 503 sem Redis local, comportamento esperado. O cenário 200 foi
  verificado em teste de requisição com broker simulado.

## Requisição oficial limitada

`scripts/smoke_live.py` consultou o catálogo CONITEC (132 itens), selecionou apenas
Acidentes Escorpiônicos e baixou o PDF oficial. Resultado: 2.659.178 bytes,
50 páginas, 110.609 caracteres extraídos, job COMPLETED e entrega duplicada IGNORED.
RAW recuperado e hash conferido antes de remover o banco/volume temporários do teste.

Origem: https://www.gov.br/conitec/pt-br/midias/protocolos/pcdt-acidentes-escorpionicos/@@display-file/file

SHA-256 RAW: `17f6427eb1b348e4f294240eb5a0e2986c02e0b20f8f6ac668e73dd0e3ec8d5b`.
Relatórios locais: `test-results/live-smoke.json`, `http-smoke.json`, `postgres.xml`.
O snapshot HTML de quatro entradas oficiais está nos fixtures versionados.

## Limites desta execução

Docker/Compose e Redis não estão instalados na máquina. Não foi executado build
da imagem nem inicialização do Compose localmente. O teste de entrega Celery com
Redis real é pulado sem TEST_REDIS_URL. Build, healthchecks e smoke do Compose
permanecem como validações manuais em uma máquina com Docker. ARM64 não validado.
O projeto usa apenas execução local; os arquivos dev/prod e o workflow de CI foram
removidos conforme a orientação do usuário.
Após essa simplificação, a estrutura YAML do Compose, mounts, dependências e
exposição local foram conferidos; os cinco testes de requisição da API passaram.
Essa conferência de configuração não substitui iniciar os containers com Docker.

Há um aviso de depreciação do TestClient da versão instalada de Starlette em relação
ao httpx. Os testes passam; não foi introduzida outra biblioteca HTTP para suprimi-lo.

## Limites funcionais

Identidade CONITEC deriva do título clínico; renomeações precisam de reconciliação
manual para evitar uma nova identidade. A política inicial inclui o principal e
anexos explícitos; portarias/resumos ficam fora do hash textual. OCR é revisão futura.
