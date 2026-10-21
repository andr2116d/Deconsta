# Imagen del client: compila la SPA y la sirve con Caddy, que además reenvía /api al server. Se
# construye desde la raíz del repositorio (lockfile y workspace de pnpm):
#   docker build -f client/Dockerfile .

FROM node:22-alpine AS construccion
# Sin hooks de Git: la imagen no tiene .git.
ENV HUSKY=0
RUN corepack enable
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY client/package.json client/
RUN pnpm install --frozen-lockfile --filter client
COPY client client
RUN pnpm --filter client build-only

FROM caddy:2-alpine
COPY client/Caddyfile /etc/caddy/Caddyfile
COPY --from=construccion /repo/client/dist /srv
