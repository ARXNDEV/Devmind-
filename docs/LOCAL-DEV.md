# Local development

```bash
corepack enable
pnpm install
cp .env.example .env
pnpm infra:up
pnpm dev
```

## Services

| Service | Port | Notes |
| --- | --- | --- |
| web | 3000 | Next.js |
| api | 4000 | NestJS, Swagger at /docs |
| code-intel | 8000 | FastAPI, OpenAPI at /docs |
| postgres | 5432 | |
| redis | 6379 | |
| neo4j | 7474 / 7687 | browser / bolt |
| qdrant | 6333 | |

Stop everything with `pnpm infra:down`.
