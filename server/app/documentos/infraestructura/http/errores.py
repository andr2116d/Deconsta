from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errores import respuesta_error
from app.documentos.dominio.errores import (
    ArchivoDemasiadoGrande,
    ArchivoFaltante,
    ArchivoInvalido,
    AsistenteNoEncontrada,
    BloqueoNoEncontrado,
    ContenidoNoDisponible,
    DocumentoNoEncontrado,
    DocumentoYaRegistrado,
    ErrorDocumentos,
    RegistroBloqueado,
)

ESTADOS_HTTP: dict[type[ErrorDocumentos], int] = {
    RegistroBloqueado: 403,
    DocumentoNoEncontrado: 404,
    BloqueoNoEncontrado: 404,
    AsistenteNoEncontrada: 404,
    DocumentoYaRegistrado: 409,
    ArchivoDemasiadoGrande: 413,
    ArchivoFaltante: 422,
    ContenidoNoDisponible: 503,
}


def estado_de(exc: ErrorDocumentos) -> int:
    estado = ESTADOS_HTTP.get(type(exc))
    if estado is None and isinstance(exc, ArchivoInvalido):
        return 422
    return estado or 400


async def manejar_error_documentos(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ErrorDocumentos)
    extra: dict[str, object] = {}
    if isinstance(exc, DocumentoYaRegistrado):
        # Dice en qué deuda se usó, para que la persona la reconozca y cambie de documento.
        extra["existing_debt"] = {
            "id": str(exc.deuda.id),
            "concepto": exc.deuda.concepto,
            "registrada_en": exc.deuda.registrada_en.isoformat(),
        }
        extra["registration_blocked"] = exc.registro_bloqueado
    if isinstance(exc, RegistroBloqueado):
        extra["blocked_since"] = exc.desde.isoformat()
    return respuesta_error(estado_de(exc), exc.codigo, exc.mensaje, campos=exc.campos, extra=extra)


def respuesta_archivo_grande() -> JSONResponse:
    """La que da el tope del cuerpo de POST /documentos, antes de leer el archivo."""
    error = ArchivoDemasiadoGrande()
    return respuesta_error(413, error.codigo, error.mensaje, campos=error.campos)


def registrar_manejadores_documentos(app: FastAPI) -> None:
    app.add_exception_handler(ErrorDocumentos, manejar_error_documentos)
