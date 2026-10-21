# Deconsta

Sistema web para que un gerente delegue a su asistente el pago de servicios y deudas, con órdenes
de pago, límites y aprobaciones, comprobantes y notificaciones en tiempo real.

| Carpeta | Contenido |
|---|---|
| `client/` | Interfaz web: Vue 3, Vite y TypeScript. Ver [client/README.md](client/README.md) |
| `server/` | API (FastAPI, SQLAlchemy y migraciones SQL versionadas), worker y Beat de Celery. Ver [server/README.md](server/README.md) |
| `docker/` | Configuración de los servicios locales de `compose.yaml` |

La especificación, las historias y la guía de trabajo están en Notion.

## Desarrollo local

Requisitos: Node (versión de `.nvmrc`) con corepack, uv y Docker.

```bash
corepack enable
pnpm install
(cd server && uv sync)
cp server/.env.example server/.env   # y genera CLAVE_CIFRADO_DATOS y CLAVE_HUELLA_DATOS
pnpm services:up                      # Postgres, Redis, Mailpit y SeaweedFS
pnpm init:gerente --nombres ...       # crea el primer gerente; ver server/README.md
pnpm dev                              # client, server, worker y Beat
```

La API aplica las migraciones pendientes al arrancar. El client queda en http://localhost:5173 y
llama a la API por el proxy de Vite. Antes de abrir
una PR, `pnpm check` ejecuta el lint y las pruebas de las dos partes.
