# Deployment Runbook

DevMind runs as a self-contained Docker Compose stack — five data stores, a
local model server (Ollama), and three application services. **No external API
keys are required**; all inference is local ([ADR-0008](adr/0008-local-model-serving.md)).

This runbook covers the current target: an enterprise VM reachable only through
the HySecure VPN, where SSH (port 22) is blocked by gateway policy, so the repo
is operated **directly from the VM's terminal**.

## Prerequisites on the VM

- Linux x86_64 with `sudo`, `curl`, and `openssl`.
- Outbound HTTPS during first setup (to install Docker and pull base images +
  models). After that the platform runs fully offline.
- Disk: ~15 GB for images + models (more for indexed repositories).
- RAM: 8 GB minimum for CPU inference with a small model; 16 GB+ recommended.
  A GPU is auto-detected by Ollama and used if present.

## Getting the code onto the VM (no SSH)

Pick whichever your environment allows:

1. **Git** — if the VM can reach your git host: `git clone <repo-url>`.
2. **Git bundle** — on the Mac: `git bundle create devmind.bundle --all`; move
   the single `devmind.bundle` file to the VM by any allowed channel (HySecure
   file transfer, shared folder, USB), then `git clone devmind.bundle devmind`.
3. **Archive** — `git archive --format=tar.gz -o devmind.tgz HEAD`; transfer and
   extract.

## One-command bootstrap

From the repository root on the VM:

```bash
chmod +x infra/bootstrap-vm.sh
./infra/bootstrap-vm.sh
```

The script is idempotent and:

1. Installs Docker + Compose v2 if absent.
2. On first run, generates `.env` from `.env.example` with fresh secrets and
   rewrites `localhost` hostnames to container names.
3. Starts the data stores and Ollama.
4. Pulls the configured models (`minio-init`, `ollama-init` one-shots).
5. Builds and starts `api`, `code-intel`, workers, and `web`; the `migrate`
   one-shot applies database migrations before `api` starts.
6. Waits for `/readyz`.

### CPU-only VMs

The default generation model is `qwen2.5-coder:7b`. On a CPU-only box, use a
smaller model:

```bash
LLM_MODEL=qwen2.5-coder:3b ./infra/bootstrap-vm.sh    # or :1.5b for low RAM
```

Embeddings (`nomic-embed-text`) run comfortably on CPU regardless.

## Verifying the deployment

```bash
# All dependencies healthy (postgres, redis, qdrant, neo4j, minio, ollama):
curl -s http://localhost:4000/readyz | python3 -m json.tool

# Local models loaded and ready (no API key involved):
TOKEN=$(grep '^INTERNAL_SERVICE_TOKEN=' .env | cut -d= -f2)
curl -s -H "x-internal-token: $TOKEN" http://localhost:8000/internal/v1/models | python3 -m json.tool
```

`embedding.ready` and `generation.ready` become `true` once the respective
models finish pulling. Then open the web UI at `http://localhost:3000`, register
an organization, and create a project.

## Operations

| Task | Command (from repo root) |
| --- | --- |
| View status | `docker compose -f infra/docker-compose.yml -f infra/docker-compose.apps.yml ps` |
| Tail a service | `docker compose ... logs -f code-intel` |
| Restart a service | `docker compose ... restart api` |
| Change model | edit `CI_LLM_MODEL` in `.env`, then `docker compose ... up ollama-init && docker compose ... restart code-intel ci-worker` |
| Stop everything | `docker compose ... down` (add `-v` to also drop data) |

## Security notes for pilots

- All host ports bind to `127.0.0.1` only. To expose the UI, front it with a
  TLS-terminating reverse proxy (Caddy/Traefik) — never expose `code-intel`,
  the databases, or Ollama directly.
- `.env` holds generated secrets; treat it as sensitive and back it up
  out-of-band. Rotate `INTERNAL_SERVICE_TOKEN` and `API_JWT_SECRET` per policy.
- Postgres is the only store needing backup; Neo4j and Qdrant are rebuildable
  by re-indexing, and Ollama models are re-pullable
  ([09-deployment-and-operations](architecture/09-deployment-and-operations.md)).
