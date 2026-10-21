"""Registro de la API: cada solicitud recibe un identificador que aparece en los logs y en la
cabecera X-Request-ID. Los logs no incluyen cuerpos de solicitud, contraseñas ni datos personales.
"""

import logging
import logging.config
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from fastapi import Request, Response

from app.core.errores import respuesta_error_interno

logger = logging.getLogger(__name__)

id_solicitud: ContextVar[str] = ContextVar("id_solicitud", default="-")


class FiltroSolicitud(logging.Filter):
    def filter(self, registro: logging.LogRecord) -> bool:
        registro.id_solicitud = id_solicitud.get()
        return True


def configurar_registro(nivel: str) -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"solicitud": {"()": FiltroSolicitud}},
            "formatters": {
                "simple": {
                    "format": "%(asctime)s %(levelname)s [%(id_solicitud)s] %(name)s: %(message)s"
                }
            },
            "handlers": {
                "consola": {
                    "class": "logging.StreamHandler",
                    "formatter": "simple",
                    "filters": ["solicitud"],
                }
            },
            "loggers": {"app": {"handlers": ["consola"], "level": nivel, "propagate": False}},
        }
    )


def crear_middleware_seguridad(
    hsts: bool,
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    async def middleware(
        request: Request, siguiente: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        referencia = uuid.uuid4().hex
        request.state.id_solicitud = referencia
        token = id_solicitud.set(referencia)
        try:
            respuesta = await siguiente(request)
        except Exception:
            # La traza queda en el log del servidor; el cliente solo recibe la referencia.
            logger.exception("Error no controlado en %s %s", request.method, request.url.path)
            respuesta = respuesta_error_interno(referencia)
        finally:
            id_solicitud.reset(token)
        cabeceras = respuesta.headers
        cabeceras["X-Request-ID"] = referencia
        cabeceras["X-Content-Type-Options"] = "nosniff"
        cabeceras["X-Frame-Options"] = "DENY"
        cabeceras["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            # Las respuestas de la API pueden llevar datos personales: no se guardan en caché.
            cabeceras["Cache-Control"] = "no-store"
        if hsts:
            cabeceras["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return respuesta

    return middleware
