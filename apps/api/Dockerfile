# syntax=docker/dockerfile:1
# Multi-stage build; same image serves API and worker (command override).

FROM node:22-slim AS base
RUN corepack enable
WORKDIR /repo

FROM base AS deps
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY apps/api/package.json apps/api/
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile --filter @devmind/api

FROM deps AS build
COPY apps/api apps/api
# pnpm v10 requires --legacy for deploy from a non-injected workspace.
RUN pnpm --filter @devmind/api build && \
    pnpm --filter @devmind/api --prod --legacy deploy /out

FROM node:22-slim AS runtime
ENV NODE_ENV=production
RUN groupadd -r devmind && useradd -r -g devmind devmind
WORKDIR /app
COPY --from=build /out/dist ./dist
COPY --from=build /out/node_modules ./node_modules
COPY --from=build /out/package.json ./package.json
USER devmind
EXPOSE 4000
CMD ["node", "dist/main.js"]
