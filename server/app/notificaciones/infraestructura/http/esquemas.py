from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.notificaciones.aplicacion.notificaciones import Bandeja
from app.notificaciones.dominio.modelos import Notificacion, TipoNotificacion


class NotificacionSalida(BaseModel):
    id: UUID
    tipo: TipoNotificacion
    titulo: str
    cuerpo: str
    deuda_id: UUID | None
    cuenta_id: UUID | None
    creada_en: datetime
    leida: bool

    @classmethod
    def desde(cls, notificacion: Notificacion) -> "NotificacionSalida":
        return cls(
            id=notificacion.id,
            tipo=notificacion.tipo,
            titulo=notificacion.titulo,
            cuerpo=notificacion.cuerpo,
            deuda_id=notificacion.deuda_id,
            cuenta_id=notificacion.cuenta_id,
            creada_en=notificacion.creada_en,
            leida=notificacion.leida,
        )


class BandejaSalida(BaseModel):
    notificaciones: list[NotificacionSalida]
    no_leidas: int

    @classmethod
    def desde(cls, bandeja: Bandeja) -> "BandejaSalida":
        return cls(
            notificaciones=[NotificacionSalida.desde(n) for n in bandeja.notificaciones],
            no_leidas=bandeja.no_leidas,
        )


class MarcadasSalida(BaseModel):
    marcadas: int
