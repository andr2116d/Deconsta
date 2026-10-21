"""Tope del cuerpo de las solicitudes.

Los formularios de la API pesan unos cientos de bytes: un cuerpo enorme solo sirve para gastar
memoria y CPU del servidor. Se rechaza antes de leerlo si declara su tamaño (Content-Length) y,
si llega por partes, en cuanto supera el tope. Las rutas de archivos tienen su propio tope y su
propia respuesta: a quien sube un documento se le dice que el archivo es grande, no la solicitud.
"""

from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.errores import respuesta_error

TAMANO_MAXIMO = 64 * 1024

Mensaje = MutableMapping[str, Any]
Recibir = Callable[[], Awaitable[Mensaje]]
Enviar = Callable[[Mensaje], Awaitable[None]]
AppAsgi = Callable[[MutableMapping[str, Any], Recibir, Enviar], Awaitable[None]]


def respuesta_cuerpo_grande() -> JSONResponse:
    return respuesta_error(
        413, "CUERPO_DEMASIADO_GRANDE", "La solicitud supera el tamaño permitido."
    )


@dataclass(frozen=True)
class Tope:
    maximo: int
    respuesta: Callable[[], JSONResponse] = respuesta_cuerpo_grande


class LimiteCuerpo:
    """Lee el cuerpo completo (como mucho, el tope) antes de pasarlo a la API y lo entrega
    intacto. Así un exceso se responde siempre con 413, sin importar cómo llegó."""

    def __init__(
        self,
        app: AppAsgi,
        maximo: int = TAMANO_MAXIMO,
        excepciones: Mapping[str, Tope] | None = None,
    ) -> None:
        self.app = app
        self.general = Tope(maximo)
        # Tope propio de algunas rutas exactas (POST de un archivo), por su ruta.
        self.excepciones = dict(excepciones or {})

    async def __call__(
        self, scope: MutableMapping[str, Any], receive: Recibir, send: Enviar
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        tope = self.excepciones.get(scope["path"], self.general)
        declarado = dict(scope["headers"]).get(b"content-length", b"")
        if declarado.isdigit() and int(declarado) > tope.maximo:
            await tope.respuesta()(scope, receive, send)
            return
        cuerpo = bytearray()
        while True:
            mensaje = await receive()
            if mensaje["type"] == "http.disconnect":
                return
            cuerpo += mensaje.get("body", b"")
            if len(cuerpo) > tope.maximo:
                await tope.respuesta()(scope, receive, send)
                return
            if not mensaje.get("more_body", False):
                break
        entregado = False

        async def recibir() -> Mensaje:
            nonlocal entregado
            if entregado:
                return await receive()
            entregado = True
            return {"type": "http.request", "body": bytes(cuerpo), "more_body": False}

        await self.app(scope, recibir, send)


def limitar_cuerpo(
    app: FastAPI, maximo: int = TAMANO_MAXIMO, excepciones: Mapping[str, Tope] | None = None
) -> None:
    app.add_middleware(LimiteCuerpo, maximo=maximo, excepciones=excepciones)
