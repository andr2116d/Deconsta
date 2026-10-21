from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errores import respuesta_error
from app.pagos.dominio.errores import (
    BloqueoPagosNoEncontrado,
    CamposFaltantes,
    ComprobanteNoEncontrado,
    ComprobanteNoUsable,
    ComprobantesNoCombinan,
    CuotaNoPagable,
    ErrorPagos,
    ImporteNoCoincide,
    PagoInvalido,
    PagoNoEncontrado,
    PagoYaDecidido,
    RegistroPagosBloqueado,
)

ESTADOS_HTTP: dict[type[ErrorPagos], int] = {
    RegistroPagosBloqueado: 403,
    ComprobanteNoEncontrado: 404,
    BloqueoPagosNoEncontrado: 404,
    PagoNoEncontrado: 404,
    PagoYaDecidido: 409,
    CuotaNoPagable: 409,
    ComprobanteNoUsable: 409,
    CamposFaltantes: 422,
    PagoInvalido: 422,
    ComprobantesNoCombinan: 422,
    ImporteNoCoincide: 422,
}


async def manejar_error_pagos(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ErrorPagos)
    extra: dict[str, object] = {}
    if isinstance(exc, RegistroPagosBloqueado):
        extra["blocked_since"] = exc.desde.isoformat()
    return respuesta_error(
        ESTADOS_HTTP.get(type(exc), 400), exc.codigo, exc.mensaje, campos=exc.campos, extra=extra
    )


def registrar_manejadores_pagos(app: FastAPI) -> None:
    app.add_exception_handler(ErrorPagos, manejar_error_pagos)
