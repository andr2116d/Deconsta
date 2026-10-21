import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from app.acceso.infraestructura.http.errores import registrar_manejadores_acceso
from app.api.v1 import router as api_v1
from app.categorias.infraestructura.http.errores import registrar_manejadores_categorias
from app.contenedor import Contenedor
from app.core.config import Settings, settings
from app.core.cuerpo import limitar_cuerpo
from app.core.errores import registrar_manejadores
from app.core.migraciones import aplicar_pendientes
from app.core.registro import configurar_registro, crear_middleware_seguridad
from app.documentos.dominio.modelos import TAMANO_MAXIMO
from app.documentos.infraestructura.http.errores import registrar_manejadores_documentos
from app.notificaciones.infraestructura.http.errores import registrar_manejadores_notificaciones
from app.reglas.infraestructura.http.errores import registrar_manejadores_reglas

logger = logging.getLogger(__name__)


def crear_app(config: Settings = settings, contenedor: Contenedor | None = None) -> FastAPI:
    configurar_registro(config.nivel_registro)
    contenedor = contenedor or Contenedor.crear(config)

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
        # Si una migración falla, la excepción detiene el arranque: la API no atiende con un
        # esquema incompleto.
        if config.migrar_al_iniciar:
            await run_in_threadpool(aplicar_pendientes, config.database_url)
        yield
        contenedor.cerrar()

    produccion = config.entorno == "produccion"
    app = FastAPI(
        title="Deconsta",
        lifespan=ciclo_de_vida,
        docs_url=None if produccion else "/docs",
        redoc_url=None,
        openapi_url=None if produccion else "/openapi.json",
    )
    app.state.contenedor = contenedor
    registrar_manejadores(app)
    registrar_manejadores_acceso(app)
    registrar_manejadores_categorias(app)
    registrar_manejadores_reglas(app)
    registrar_manejadores_documentos(app)
    registrar_manejadores_notificaciones(app)
    # Antes que el de seguridad: así un 413 también lleva sus cabeceras. Solo la subida de
    # documentos admite un archivo; el margen cubre las cabeceras del multipart.
    limitar_cuerpo(app, excepciones={"/api/v1/documentos": TAMANO_MAXIMO + 64 * 1024})
    app.middleware("http")(crear_middleware_seguridad(hsts=produccion))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(api_v1, prefix="/api/v1")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = crear_app()
