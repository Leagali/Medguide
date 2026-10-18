# ADR 002 — Artefatos e versões observadas

Status: aceito, 17/10/2026.

RAW é gravado atomicamente antes da extração e identificado por SHA-256.
Artefatos registram cada coleta, inclusive bytes novos com texto idêntico.
Versões usam hash de páginas normalizadas e composição ordenada por chave/papel.
Metadados e datas oficiais permanecem nas observações. Nunca reconstruímos versões
anteriores à primeira coleta. Texto vazio exige revisão e preserva os originais.

A constraint histórica de hash evita duplicar conteúdo que reaparece: uma reversão
aponta a versão corrente para a versão já conhecida e registra CONTENT_REVERTED no
job. A cronologia dos jobs/artefatos preserva a nova observação desse conteúdo.
