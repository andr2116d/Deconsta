import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.api.v1 import router as api_v1
from app.core.config import Settings, settings
from app.core.migraciones import aplicar_pendientes

logger = logging.getLogger(__name__)


def crear_app(config: Settings = settings) -> FastAPI:
    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
        # Si una migración falla, la excepción detiene el arranque: la API no atiende con un
        # esquema incompleto.
        if config.migrar_al_iniciar:
            await run_in_threadpool(aplicar_pendientes, config.database_url)
        yield

    app = FastAPI(title="Control de Pagos", lifespan=ciclo_de_vida)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_v1, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = crear_app()
