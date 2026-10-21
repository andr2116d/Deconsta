# Deconsta

Sistema web para que un gerente delegue a su asistente el pago de servicios y deudas, con órdenes
de pago, límites y aprobaciones, comprobantes y notificaciones en tiempo real.

| Carpeta | Contenido |
|---|---|
| `client/` | Interfaz web: Vue 3, Vite y TypeScript. Ver [client/README.md](client/README.md) |
| `server/` | API (FastAPI, SQLAlchemy y migraciones SQL versionadas) y worker de Celery. Ver [server/README.md](server/README.md) |
| `docker/` | Configuración de los servicios locales de `compose.yaml` |

La especificación, las historias y la guía de trabajo están en Notion.

## Desarrollo local

Requisitos: Node (versión de `.nvmrc`) con corepack, uv y Docker.

```bash
corepack enable
pnpm install
(cd server && uv sync --group ocr)
cp server/.env.example server/.env   # y genera las tres claves CLAVE_*
pnpm services:up                      # Postgres, Redis y SeaweedFS
pnpm init:gerente --nombres ...       # crea el primer gerente; ver server/README.md
pnpm dev                              # client, server y worker OCR
```

Para probar la revisión con IA sin clave de la API, pon `IA_PROVEEDOR=claude_code` en
`server/.env` y ten iniciada tu sesión de Claude Code (`claude`): el worker la usa para revisar los
documentos. En producción solo se usa `ANTHROPIC_API_KEY`. Si un puerto (8000 o 5173) está ocupado
por otro proceso, `pnpm dev` se detiene en vez de arrancar a medias.

La API aplica las migraciones pendientes al arrancar. El client queda en http://localhost:5173 y
llama a la API por el proxy de Vite. Antes de abrir
una PR, `pnpm check` ejecuta el lint y las pruebas de las dos partes.
