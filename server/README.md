# server

API de Control de Pagos con FastAPI. Las dependencias se manejan con [uv](https://docs.astral.sh/uv/).

## Preparar

```sh
uv sync                # crea .venv e instala dependencias (incluye el grupo dev)
cp .env.example .env
```

## Comandos

```sh
uv run uvicorn app.main:app --reload --port 8000   # servidor en desarrollo
uv run celery -A app.workers.celery_app:celery_app worker -Q general --loglevel=INFO
uv run pytest                                      # tests
uv run ruff check . && uv run ruff format .        # lint y formato
uv run mypy app                                    # tipos
```

## Dependencias

```sh
uv add <paquete>           # dependencia de producción
uv add --dev <paquete>     # dependencia de desarrollo
uv remove <paquete>
uv lock --upgrade          # actualizar versiones
```
