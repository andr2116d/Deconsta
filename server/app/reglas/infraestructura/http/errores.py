from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errores import respuesta_error
from app.reglas.dominio.errores import (
    AutorizacionNoDeclarada,
    ErrorReglas,
    LimiteTitulares,
    ReglaInvalida,
    SinCambios,
    TitularDuplicado,
    TitularEsGerente,
    TitularNoEncontrado,
)

ESTADOS_HTTP: dict[type[ErrorReglas], int] = {
    TitularNoEncontrado: 404,
    TitularDuplicado: 409,
    LimiteTitulares: 409,
    ReglaInvalida: 422,
    SinCambios: 422,
    AutorizacionNoDeclarada: 422,
    TitularEsGerente: 422,
}


async def manejar_error_reglas(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ErrorReglas)
    return respuesta_error(
        ESTADOS_HTTP.get(type(exc), 400), exc.codigo, exc.mensaje, campos=exc.campos
    )


def registrar_manejadores_reglas(app: FastAPI) -> None:
    app.add_exception_handler(ErrorReglas, manejar_error_reglas)
