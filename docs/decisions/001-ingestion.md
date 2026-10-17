# ADR 001 — Monólito modular de ingestão

Status: aceito para o MVP de ingestão, 17/10/2026.

Manter o frontend React e adicionar Python/FastAPI, PostgreSQL e Celery/Redis
com processos separados. Conectores homologados em registry estático; nenhum
import arbitrário configurado pelo banco. Cada etapa será validada antes do commit.

Consequências: mesma imagem para API/workers/Beat/migração; novos conectores
implementam contratos comuns. Compose atende servidor único, sem promessa de HA.
