# syntax=docker/dockerfile:1
# Same image runs the API (default CMD) and the arq worker (command override).

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY services/code-intel/pyproject.toml services/code-intel/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
COPY services/code-intel/src ./src
COPY services/code-intel/README.md ./README.md
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
# git is required to clone repositories for indexing (a core function).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd -r devmind && useradd -r -g devmind devmind
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY --from=build /app/src /app/src
USER devmind
EXPOSE 8000
CMD ["uvicorn", "devmind_code_intel.main:app", "--host", "0.0.0.0", "--port", "8000"]
