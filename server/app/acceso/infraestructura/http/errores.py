from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.acceso.dominio.errores import (
    AsistenteEliminadaRegistrada,
    CambioDocumentoSinConfirmar,
    ContrasenaActualIncorrecta,
    ContrasenaInsegura,
    ContrasenaRepetida,
    ContrasenaRequerida,
    CredencialesIncorrectas,
    CuentaBloqueada,
    CuentaNoBloqueada,
    CuentaNoEliminada,
    CuentaNoEncontrada,
    CuentaYaBloqueada,
    DatosDuplicados,
    DatosInvalidos,
    DatosYaConfirmados,
    DemasiadasSolicitudes,
    DocumentoNoModificable,
    DocumentosDesactualizados,
    ErrorAcceso,
    IncorporacionPendiente,
    LimiteCambiosNombreUsuario,
    NoAutenticado,
    PersonaYaEnEquipo,
    ServicioNoDisponible,
    SinCambios,
    SinPermiso,
)
from app.core.errores import respuesta_error

ESTADOS_HTTP: dict[type[ErrorAcceso], int] = {
    CredencialesIncorrectas: 401,
    NoAutenticado: 401,
    ContrasenaActualIncorrecta: 400,
    SinPermiso: 403,
    IncorporacionPendiente: 403,
    CuentaNoEncontrada: 404,
    CuentaNoBloqueada: 409,
    DatosDuplicados: 409,
    DocumentosDesactualizados: 409,
    LimiteCambiosNombreUsuario: 409,
    CuentaYaBloqueada: 409,
    PersonaYaEnEquipo: 409,
    AsistenteEliminadaRegistrada: 409,
    CuentaNoEliminada: 409,
    DatosYaConfirmados: 409,
    ContrasenaInsegura: 422,
    ContrasenaRepetida: 422,
    DatosInvalidos: 422,
    SinCambios: 422,
    ContrasenaRequerida: 422,
    DocumentoNoModificable: 422,
    CambioDocumentoSinConfirmar: 422,
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
    if isinstance(exc, IncorporacionPendiente):
        extra["pending_steps"] = exc.pasos
    if isinstance(exc, AsistenteEliminadaRegistrada):
        extra["deleted_account"] = {
            "id": str(exc.asistente_id),
            "nombre_usuario": exc.nombre_usuario,
        }
    if isinstance(exc, LimiteCambiosNombreUsuario):
        extra["renews_at"] = exc.renueva_en.isoformat()
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
