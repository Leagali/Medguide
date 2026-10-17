# Arquitetura de ingestão MedGuide

O frontend React existente é independente do monólito modular Python 3.12.
API FastAPI, Beat e dois workers usam a mesma imagem. PostgreSQL é a fonte
durável; Redis transporta apenas IDs. RAW fica em volume com endereçamento SHA-256.

## Plano e validação

1. Infraestrutura e contratos: lock uv, modelos, migração Alembic, Compose;
   verificar constraints, migrações e validação dos contratos.
2. Descoberta CONITEC: parser de tabelas A–Z e HTTP restrito; testar fixtures
   com notas, datas ausentes, anexos e layout incompatível.
3. Ingestão: preservar RAW, extrair páginas, normalizar e versionar;
   testar bytes alterados com mesmo texto, texto alterado, múltiplos arquivos,
   extração vazia e reexecução.
4. Execução assíncrona: claims com lease, filas, reconciliador e API restrita;
   testar mensagens repetidas, interrupção, retries e requisições administrativas.
5. Hardening: conector simulado com três passos, SSRF, CI, smoke real limitado
   e documentação operacional.

O catálogo será verificado diariamente e o conteúdo a cada 30 dias por padrão.
As frequências são configuráveis. Não há autenticação de usuários ou IA;
operações administrativas usam um segredo de serviço.

## Etapa 0

Contratos validados, tabelas com constraints de identidade/execução ativa,
configuração por ambiente e processos Compose definidos. Frontend preservado.

## Etapa 1

Parser A–Z e registry CONITEC implementados. Requisição real ao catálogo encontrou
132 itens. A identidade inicial é o título clínico normalizado com hash, sem nota
de alteração: mudanças de título precisam de revisão para mesclar identidades.
PCDT principal e anexos explícitos integram a versão; portarias e resumos ficam
somente no texto de metadados. Itens sem link tornam-se candidatos para revisão.
HTTP fixa o IP público validado, mantém TLS/SNI original, valida cada redirect,
respeita robots e limita tamanho/tentativas. 18 testes de parser/HTTP passaram.

## Etapa 2

Storage atômico por SHA-256, extração PDF por página, HTML explicitamente marcado,
normalização Unicode/espaços e composição de múltiplos documentos implementados.
Originais são persistidos antes da extração; páginas brutas e versões dos parsers
ficam auditáveis. Observações de metadados e artefatos não geram versões falsas.
Uma reversão de conteúdo aponta para a versão histórica existente e fica registrada
no resultado do job. Atualização da versão corrente é transacional.
