"""Respuestas de error con una estructura única para toda la API:

    {"code": "CODIGO_ESTABLE", "detail": "Mensaje para la persona usuaria.", "fields": {...}}

`fields` aparece solo cuando el error apunta a campos concretos. Los errores internos se registran
con una referencia que también recibe el cliente, sin trazas ni datos de la solicitud.
"""

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)

UBICACIONES = {"body", "query", "path", "header", "cookie"}
OBLIGATORIOS = {"missing", "obligatorio"}
# Errores propios de los esquemas: su mensaje ya está escrito para la persona usuaria.
CON_MENSAJE_PROPIO = {"obligatorio", "caracteres_invalidos"}

CODIGOS_HTTP = {
    401: ("NO_AUTENTICADO", "Inicia sesión para continuar."),
    403: ("SIN_PERMISO", "No tienes permiso para realizar esta acción."),
    404: ("NO_ENCONTRADO", "No encontramos lo que buscas."),
    405: ("METODO_NO_PERMITIDO", "Esta operación no está permitida."),
}


def respuesta_error(
    estado: int,
    codigo: str,
    mensaje: str,
    *,
    campos: Mapping[str, str] | None = None,
    encabezados: Mapping[str, str] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> JSONResponse:
    contenido: dict[str, Any] = {"code": codigo, "detail": mensaje}
    if campos:
        contenido["fields"] = dict(campos)
    contenido.update(extra or {})
    return JSONResponse(status_code=estado, content=contenido, headers=dict(encabezados or {}))


def _mensaje_validacion(error: Mapping[str, Any]) -> str:
    tipo = error["type"]
    contexto = error.get("ctx") or {}
    if tipo in CON_MENSAJE_PROPIO:
        return str(error["msg"])
    if tipo == "missing":
        return "Este campo es obligatorio."
    if tipo == "string_too_long":
        return f"Usa como máximo {contexto.get('max_length')} caracteres."
    if tipo == "string_type":
        return "Debe ser un texto."
    if tipo == "uuid_parsing":
        return "El identificador no es válido."
    return "El valor no es válido."


async def manejar_validacion(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errores = list(exc.errors())
    if any(error["type"] == "json_invalid" for error in errores):
        return respuesta_error(
            422, "DATOS_INVALIDOS", "El cuerpo de la solicitud no es un JSON válido."
        )
    campos: dict[str, str] = {}
    for error in errores:
        ruta = [str(parte) for parte in error["loc"] if parte not in UBICACIONES]
        campos.setdefault(".".join(ruta) or "solicitud", _mensaje_validacion(error))
    if all(error["type"] in OBLIGATORIOS for error in errores):
        return respuesta_error(
            422, "CAMPOS_OBLIGATORIOS", "Completa los campos obligatorios.", campos=campos
        )
    return respuesta_error(422, "DATOS_INVALIDOS", "Revisa los datos marcados.", campos=campos)


async def manejar_http(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    codigo, mensaje = CODIGOS_HTTP.get(
        exc.status_code, ("ERROR", "No pudimos atender la solicitud.")
    )
    return respuesta_error(exc.status_code, codigo, mensaje, encabezados=exc.headers)


async def manejar_base_no_disponible(request: Request, exc: Exception) -> JSONResponse:
    # Sin la URL ni el mensaje del driver: pueden incluir host y usuario de la base.
    logger.error("La base de datos no responde (%s)", type(exc).__name__)
    return respuesta_error(
        503,
        "SERVICIO_NO_DISPONIBLE",
        "El servicio no está disponible en este momento. Inténtalo de nuevo en unos minutos.",
        extra={"reference": getattr(request.state, "id_solicitud", None)},
    )


def respuesta_error_interno(referencia: str) -> JSONResponse:
    return respuesta_error(
        500,
        "ERROR_INTERNO",
        "Ocurrió un error inesperado. Inténtalo de nuevo; si continúa, comparte esta referencia "
        "con soporte.",
        extra={"reference": referencia},
    )


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, manejar_validacion)
    app.add_exception_handler(HTTPException, manejar_http)
    app.add_exception_handler(OperationalError, manejar_base_no_disponible)
