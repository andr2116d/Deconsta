from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errores import respuesta_error
from app.deudas.dominio.errores import (
    CategoriaNoDisponible,
    DeudaInvalida,
    DeudaNoEncontrada,
    DocumentoNoRegistrable,
    ErrorDeudas,
    TransicionInvalida,
)

ESTADOS_HTTP: dict[type[ErrorDeudas], int] = {
    DeudaNoEncontrada: 404,
    DocumentoNoRegistrable: 409,
    TransicionInvalida: 409,
    DeudaInvalida: 422,
    CategoriaNoDisponible: 422,
}


async def manejar_error_deudas(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ErrorDeudas)
    return respuesta_error(
        ESTADOS_HTTP.get(type(exc), 400), exc.codigo, exc.mensaje, campos=exc.campos
    )


def registrar_manejadores_deudas(app: FastAPI) -> None:
    app.add_exception_handler(ErrorDeudas, manejar_error_deudas)
