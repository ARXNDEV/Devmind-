#!/usr/bin/env bash
# DevMind VM bootstrap — run directly on the target VM's terminal.
#
# Idempotent: safe to re-run. Installs Docker if missing, provisions .env with
# generated secrets on first run, brings up the full stack, pulls the local
# models, and runs database migrations. No SSH and no API keys required.
#
#   chmod +x infra/bootstrap-vm.sh && ./infra/bootstrap-vm.sh
#
# Env knobs:
#   LLM_MODEL   (default qwen2.5-coder:7b; use :3b or :1.5b on CPU-only VMs)
#   EMBED_MODEL (default nomic-embed-text)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log() { printf '\033[1;34m[bootstrap]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[bootstrap] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# ── 1. Docker ────────────────────────────────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
  log "Docker not found — installing via get.docker.com"
  curl -fsSL https://get.docker.com | sh || die "Docker install failed"
  sudo usermod -aG docker "$USER" || true
  log "Docker installed. You may need to log out/in for group changes."
fi
docker compose version >/dev/null 2>&1 || die "docker compose v2 plugin required"

# ── 2. .env with generated secrets (first run only) ──────────────────────────
if [[ ! -f .env ]]; then
  log "Generating .env from .env.example with fresh secrets"
  gen() { openssl rand "$@"; }
  JWT="$(gen -base64 48 | tr -d '\n')"
  INTERNAL="$(gen -hex 24)"
  CRED_KEY="$(gen -base64 32 | tr -d '\n')"
  sed \
    -e "s|^API_JWT_SECRET=.*|API_JWT_SECRET=${JWT}|" \
    -e "s|^INTERNAL_SERVICE_TOKEN=.*|INTERNAL_SERVICE_TOKEN=${INTERNAL}|" \
    -e "s|^CI_INTERNAL_SERVICE_TOKEN=.*|CI_INTERNAL_SERVICE_TOKEN=${INTERNAL}|" \
    -e "s|^API_CREDENTIAL_KEY=.*|API_CREDENTIAL_KEY=${CRED_KEY}|" \
    .env.example > .env
  # Host-networked services address each other by container name.
  sed -i \
    -e 's|@localhost:5432|@postgres:5432|g' \
    -e 's|localhost:6379|redis:6379|g' \
    -e 's|http://localhost:6333|http://qdrant:6333|g' \
    -e 's|bolt://localhost:7687|bolt://neo4j:7687|g' \
    -e 's|http://localhost:9000|http://minio:9000|g' \
    -e 's|http://localhost:11434|http://ollama:11434|g' \
    -e 's|http://localhost:4000|http://api:4000|g' \
    -e 's|http://localhost:8000|http://code-intel:8000|g' \
    .env
  : "${LLM_MODEL:=qwen2.5-coder:7b}"
  sed -i -e "s|^CI_LLM_MODEL=.*|CI_LLM_MODEL=${LLM_MODEL}|" .env
  log ".env created. Review it before exposing this host to a network."
else
  log ".env already present — leaving it untouched"
fi

# ── 3. Bring up the full stack (stores + apps + model server) ────────────────
COMPOSE=(docker compose --env-file .env
  -f infra/docker-compose.yml -f infra/docker-compose.apps.yml)

log "Starting data stores + Ollama"
"${COMPOSE[@]}" up -d postgres redis qdrant neo4j minio ollama

log "Pulling local models (first run downloads several GB)"
"${COMPOSE[@]}" up minio-init ollama-init

log "Building and starting application services (runs migrations automatically)"
"${COMPOSE[@]}" up -d --build

log "Waiting for API readiness"
for _ in $(seq 1 30); do
  if curl -sf http://localhost:4000/readyz >/dev/null 2>&1; then
    log "API is ready"
    break
  fi
  sleep 3
done

log "Done. Web UI: http://localhost:3000  ·  API: http://localhost:4000"
log "Check model status: curl -s -H \"x-internal-token: \$(grep '^INTERNAL_SERVICE_TOKEN=' .env | cut -d= -f2)\" http://localhost:8000/internal/v1/models"
