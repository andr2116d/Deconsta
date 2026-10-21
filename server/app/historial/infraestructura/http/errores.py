from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errores import respuesta_error
from app.historial.dominio.errores import ErrorHistorial, FiltroInvalido

ESTADOS_HTTP: dict[type[ErrorHistorial], int] = {FiltroInvalido: 422}


async def manejar_error_historial(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ErrorHistorial)
    return respuesta_error(
        ESTADOS_HTTP.get(type(exc), 400), exc.codigo, exc.mensaje, campos=exc.campos
    )


def registrar_manejadores_historial(app: FastAPI) -> None:
    app.add_exception_handler(ErrorHistorial, manejar_error_historial)
