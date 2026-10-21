from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errores import respuesta_error
from app.notificaciones.dominio.errores import ErrorNotificaciones, NotificacionNoEncontrada

ESTADOS_HTTP: dict[type[ErrorNotificaciones], int] = {NotificacionNoEncontrada: 404}


async def manejar_error_notificaciones(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ErrorNotificaciones)
    return respuesta_error(ESTADOS_HTTP.get(type(exc), 400), exc.codigo, exc.mensaje)


def registrar_manejadores_notificaciones(app: FastAPI) -> None:
    app.add_exception_handler(ErrorNotificaciones, manejar_error_notificaciones)
