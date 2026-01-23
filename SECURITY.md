# Security Policy

## Reporting a vulnerability

Please do **not** open a public issue for security problems.
Email the maintainers privately with a description, reproduction steps and impact.
You will receive an acknowledgement within 3 business days.

## Scope

- `apps/api` — product API, authentication and authorization
- `apps/web` — web client
- `services/code-intel` — indexing engine and internal service API
- `infra/` — compose topology and bootstrap scripts

## Handling

Confirmed issues are fixed on `main` first, then noted in `CHANGELOG.md`.
See `docs/architecture/08-security.md` for the platform security posture.
