# ADR 003 — Jobs duráveis, leases e administração

Status: aceito, 17/10/2026.

PostgreSQL é a fonte de estado. Mensagens Celery/Redis contêm apenas IDs, com
acks tardios, prefetch 1 e visibility_timeout maior que o limite de tarefa.
Claims usam UPDATE condicional; token e validade do lease são conferidos em cada
persistência. Índices parciais impedem runs/jobs ativos duplicados. O reconciliador
recupera publicação perdida e workers interrompidos, com limite de tentativas.
available_at persiste backoff e Retry-After, sem countdown de longa duração.

API administrativa usa token Bearer de serviço e fecha acesso se não configurado.
Não implementa contas de usuários. Reprocessar falha cria outro job e preserva o
histórico. Homologação de URL/conector ocorre em código; a API não aceita URL livre.
Um limitador temporal Redis compartilha o espaçamento por host entre workers.
Limites e logs não representam autorização de republicação pública dos PDFs.
