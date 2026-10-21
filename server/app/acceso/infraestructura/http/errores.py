from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.acceso.dominio.errores import (
    ContrasenaActualIncorrecta,
    ContrasenaInsegura,
    ContrasenaRepetida,
    CredencialesIncorrectas,
    CuentaBloqueada,
    CuentaNoBloqueada,
    CuentaNoEncontrada,
    DatosDuplicados,
    DatosInvalidos,
    DemasiadasSolicitudes,
    ErrorAcceso,
    NoAutenticado,
    ServicioNoDisponible,
    SinPermiso,
)
from app.core.errores import respuesta_error

ESTADOS_HTTP: dict[type[ErrorAcceso], int] = {
    CredencialesIncorrectas: 401,
    NoAutenticado: 401,
    ContrasenaActualIncorrecta: 400,
    SinPermiso: 403,
    CuentaNoEncontrada: 404,
    CuentaNoBloqueada: 409,
    DatosDuplicados: 409,
    ContrasenaInsegura: 422,
    ContrasenaRepetida: 422,
    DatosInvalidos: 422,
    CuentaBloqueada: 423,
    DemasiadasSolicitudes: 429,
    ServicioNoDisponible: 503,
}


async def manejar_error_acceso(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ErrorAcceso)
    encabezados: dict[str, str] = {}
    extra: dict[str, object] = {}
    if isinstance(exc, DemasiadasSolicitudes):
        encabezados["Retry-After"] = str(exc.reintentar_en)
        extra["retry_after"] = exc.reintentar_en
    if isinstance(exc, ContrasenaInsegura):
        extra["requirements"] = list(exc.requisitos)
    respuesta = respuesta_error(
        ESTADOS_HTTP.get(type(exc), 400),
        exc.codigo,
        exc.mensaje,
        campos=exc.campos,
        encabezados=encabezados,
        extra=extra,
    )
    if isinstance(exc, NoAutenticado):
        # Una cookie vencida o revocada se borra para no seguir enviándola.
        config = request.app.state.contenedor.config
        respuesta.delete_cookie(config.cookie_sesion_nombre, path="/api")
    return respuesta


def registrar_manejadores_acceso(app: FastAPI) -> None:
    app.add_exception_handler(ErrorAcceso, manejar_error_acceso)
