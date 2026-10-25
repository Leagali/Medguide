#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

if [ ! -f .env ]; then
  cp .env.example .env
fi

session="${1:-local}"
if [[ $# -gt 1 || ! "$session" =~ ^[a-z0-9][a-z0-9-]{0,39}$ ]]; then
  printf 'Uso: bash demo/conitec/run.sh [nome-da-sessao]\n' >&2
  exit 1
fi
project="medguide-video-$session"
printf '\nMedGuide: demonstracao em http://127.0.0.1:8001\n'
printf 'Projeto isolado: %s (banco, Redis e PDFs proprios).\n' "$project"
printf 'Uma sessao nova comeca vazia. Clique em Comecar coleta CONITEC na pagina.\n'
printf 'Ctrl+C encerra esta demonstracao e preserva seus dados.\n\n'

exec docker compose --project-name "$project" \
  -f compose.yaml -f demo/conitec/compose.video.yaml \
  up demo beat worker-discovery worker-ingestion
