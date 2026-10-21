"""Avisos en tiempo real con pub/sub de Redis.

Cada cuenta tiene su canal. El mensaje solo lleva el id de la notificación: el contenido viaja por
la API, después de comprobar la sesión. Al ser compartido entre instancias, un aviso publicado por
el worker o por otra réplica de la API llega a cualquier sesión abierta.
"""

from collections.abc import AsyncIterator
from uuid import UUID

from redis import Redis
from redis import asyncio as redis_asyncio

from app.notificaciones.dominio.modelos import Notificacion

PREFIJO = "deconsta:avisos:"


def canal(destinatario_id: UUID) -> str:
    return f"{PREFIJO}{destinatario_id}"


class PublicadorRedis:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def avisar(self, notificacion: Notificacion) -> None:
        self._redis.publish(canal(notificacion.destinatario_id), str(notificacion.id))


class SuscriptorRedis:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url

    async def escuchar(self, destinatario_id: UUID) -> AsyncIterator[str]:
        cliente = redis_asyncio.Redis.from_url(self._redis_url)
        suscripcion = cliente.pubsub(ignore_subscribe_messages=True)
        try:
            await suscripcion.subscribe(canal(destinatario_id))
            while True:
                mensaje = await suscripcion.get_message(timeout=1.0)
                if mensaje is None:
                    # Cede el control para que quien consume pueda cortar o enviar un latido.
                    yield ""
                    continue
                datos = mensaje["data"]
                yield datos.decode() if isinstance(datos, bytes) else str(datos)
        finally:
            await suscripcion.aclose()
            await cliente.aclose()
