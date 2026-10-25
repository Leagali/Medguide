#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

if [ ! -f .env ]; then
  cp .env.example .env
fi

docker compose up -d
printf '\nMedGuide: interface exclusiva para o video em http://127.0.0.1:8001\n'
printf 'Ctrl+C encerra apenas o demonstrador; os servicos do acervo continuam ativos.\n\n'

exec docker compose run --rm --no-deps -T \
  --name medguide-video-demo \
  --publish 127.0.0.1:8001:8001 \
  --volume "$(pwd)/demo/conitec:/demo:ro" \
  --env MEDGUIDE_DEMO_API_URL=http://api:8000 \
  api uvicorn app:app --app-dir /demo --host 0.0.0.0 --port 8001
