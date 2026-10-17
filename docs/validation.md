# Validação da implementação — 17/10/2026

Ambiente local: Windows, Python 3.12.2, PostgreSQL 17.11 temporário escutando
somente em 127.0.0.1. Banco/arquivos de ensaio estão no diretório ignorado `data/`.
Nenhum serviço de banco foi instalado no sistema. Frontend existente preservado.

## Evidências executadas

Na validação inicial: **47 testes aprovados, 1 pulado por ausência de Redis real**;
cobertura total medida naquela execução em **87%**. O teste pulado pode ser executado manualmente
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

## Limites da primeira execução

Na primeira rodada, Docker/Compose e Redis não estavam disponíveis no terminal
Windows. O teste de entrega Celery com Redis real foi pulado sem TEST_REDIS_URL.
A validação integrada posterior no Ubuntu/WSL, descrita abaixo, resolveu essa
pendência. ARM64 permanece sem validação.
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

## Cadastro automático e CLI de fontes

Após a implementação do bootstrap e dos comandos locais: **57 testes aprovados,
1 pulado por ausência de Redis real** na suíte completa com PostgreSQL 17.11.
Ruff, formatação e mypy passaram. A cobertura não foi recalculada nesta rodada.

Novos testes verificam cadastro repetido/concorrente, preservação de desativação,
intervalos e agendamento personalizado, reutilização de run ativo, falha de publicação,
contagens por fonte e mensagens/códigos de saída da CLI. Um ensaio por subprocessos
executa migrações e bootstrap em banco SQLite novo e usa `python -m medguide` sem
token HTTP; repetir o bootstrap preserva a fonte desativada.

A estrutura YAML confirma que API, Beat e workers aguardam o término da migração
e do cadastro automático. O diagrama Draw.io foi atualizado e seu XML conferido.
Naquela etapa, a inicialização dos containers ainda dependia de validação no Ubuntu.
Essa validação foi executada na rodada integrada a seguir.

## Validação integrada no Ubuntu/WSL — 17/10/2026

Ambiente real: containers Compose em Ubuntu/WSL, Python 3.12.15, PostgreSQL e Redis.
A suíte completa executou em outro container, com banco PostgreSQL temporário e
Redis de teste isolado da aplicação: **58 testes aprovados, nenhum pulado, cobertura
total de 90%**. O banco temporário foi removido e o Redis de teste limpo ao terminar.
Lint, formatação e mypy também passaram. Resta um aviso de depreciação do TestClient.

Estado do banco de coletas: uma fonte, **132 diretrizes, 132 artefatos, 132 versões
textuais e 132 jobs COMPLETED**, sem pendências, falhas ou revisão manual.

`scripts/validate_core.py` auditou todos os documentos:

- 132 originais, totalizando 223.268.316 bytes e 9.063 páginas.
- SHA-256 do arquivo conferido contra storage_key e raw_sha256 do banco.
- Cada PDF reextraído; o hash do texto resultante coincidiu com content_sha256.
- As 132 versões tiveram composição de hashes e texto completo reconstruídos
  pelos artefatos vinculados, com igualdade exata ao banco.
- 20.776.139 caracteres de texto, sem caracteres Unicode de substituição U+FFFD.
- Textos completos de Asma, Câncer de Mama, Diabete Melito Tipo 2 e Acidentes
  Escorpiônicos foram exportados e lidos em amostras internas, além das capas.
- Versões retornadas pela API autenticada coincidiram com o texto do banco; PDFs
  retornados pelo endpoint RAW coincidiram byte a byte com o armazenamento.
- Uma página original foi renderizada e inspecionada visualmente. O parágrafo e
  seus valores numéricos foram conferidos no texto salvo da mesma página.

Uma descoberta nova, enfileirada pela API e executada pelo worker real, encontrou
132 itens e criou **zero novos jobs**. Reenvio de mensagem Celery de um job concluído
foi recebido e finalizado pelo worker sem aumentar tentativas, artefatos ou versões.
As contagens permaneceram em 132. Ambos os workers responderam ao ping Celery.

Outra coleta oficial limitada baixou novamente o PDF de Acidentes Escorpiônicos:
2.659.178 bytes, 50 páginas e 110.609 caracteres, com o mesmo hash RAW anterior.
Esse ensaio utilizou banco temporário; não criou versões falsas no banco de coletas.

`/docs`, `/openapi.json`, `/healthz` e `/readyz` responderam 200. A rejeição de token
HTTP inválido também foi verificada. Relatórios e amostras locais:
`test-results/linux-postgres-redis.xml`, `test-results/live-smoke-ubuntu.json` e
`test-results/core-validation/` (report.json, replay.json, services.json, quatro
textos completos e sample-original-page.png). Esses arquivos não são versionados.

Conclusão: o núcleo de ingestão CONITEC está funcional no ambiente local testado.
A comparação de hashes comprova integridade e consistência da extração; não é
uma revisão clínica. Texto simples perde formatação de PDF: gráficos permanecem
no original e sobrescritos podem aparecer concatenados ao texto. OCR, reconciliação
de títulos renomeados e uma tela de leitura continuam fora da implementação atual.
