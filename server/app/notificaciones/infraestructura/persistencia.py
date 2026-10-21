"""Adaptadores de Postgres para las notificaciones (SQLAlchemy Core sobre psycopg)."""

from datetime import datetime
from types import TracebackType
from typing import Any, Self
from uuid import UUID

from sqlalchemy import Connection, Engine, Row, text

from app.notificaciones.dominio.modelos import Notificacion, TipoNotificacion

COLUMNAS = """
    id, destinatario_id, tipo, clave_evento, titulo, cuerpo, creada_en, deuda_id, cuenta_id,
    leida_en
"""


def _notificacion(fila: Row[Any]) -> Notificacion:
    return Notificacion(
        id=fila.id,
        destinatario_id=fila.destinatario_id,
        tipo=TipoNotificacion(fila.tipo),
        clave_evento=fila.clave_evento,
        titulo=fila.titulo,
        cuerpo=fila.cuerpo,
        creada_en=fila.creada_en,
        deuda_id=fila.deuda_id,
        cuenta_id=fila.cuenta_id,
        leida_en=fila.leida_en,
    )


class RepositorioNotificacionesSql:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    def agregar(self, notificacion: Notificacion) -> bool:
        fila = self._conexion.execute(
            text(
                f"INSERT INTO notificacion ({COLUMNAS}) VALUES (:id, :destinatario_id, :tipo,"
                " :clave_evento, :titulo, :cuerpo, :creada_en, :deuda_id, :cuenta_id, NULL)"
                " ON CONFLICT (destinatario_id, clave_evento) DO NOTHING RETURNING id"
            ),
            {
                "id": notificacion.id,
                "destinatario_id": notificacion.destinatario_id,
                "tipo": notificacion.tipo.value,
                "clave_evento": notificacion.clave_evento,
                "titulo": notificacion.titulo,
                "cuerpo": notificacion.cuerpo,
                "creada_en": notificacion.creada_en,
                "deuda_id": notificacion.deuda_id,
                "cuenta_id": notificacion.cuenta_id,
            },
        ).first()
        return fila is not None

    def de(self, destinatario_id: UUID, limite: int) -> list[Notificacion]:
        filas = self._conexion.execute(
            text(
                f"SELECT {COLUMNAS} FROM notificacion WHERE destinatario_id = :destinatario_id"
                " ORDER BY creada_en DESC, id LIMIT :limite"
            ),
            {"destinatario_id": destinatario_id, "limite": limite},
        ).all()
        return [_notificacion(fila) for fila in filas]

    def contar_no_leidas(self, destinatario_id: UUID) -> int:
        return int(
            self._conexion.execute(
                text(
                    "SELECT count(*) FROM notificacion"
                    " WHERE destinatario_id = :destinatario_id AND leida_en IS NULL"
                ),
                {"destinatario_id": destinatario_id},
            ).scalar_one()
        )

    def marcar_leida(self, destinatario_id: UUID, notificacion_id: UUID, ahora: datetime) -> bool:
        fila = self._conexion.execute(
            text(
                "UPDATE notificacion SET leida_en = coalesce(leida_en, :ahora)"
                " WHERE id = :id AND destinatario_id = :destinatario_id RETURNING id"
            ),
            {"id": notificacion_id, "destinatario_id": destinatario_id, "ahora": ahora},
        ).first()
        return fila is not None

    def marcar_todas_leidas(self, destinatario_id: UUID, ahora: datetime) -> int:
        resultado = self._conexion.execute(
            text(
                "UPDATE notificacion SET leida_en = :ahora"
                " WHERE destinatario_id = :destinatario_id AND leida_en IS NULL"
            ),
            {"destinatario_id": destinatario_id, "ahora": ahora},
        )
        return int(resultado.rowcount)


class UnidadNotificacionesSql:
    def __init__(self, motor: Engine) -> None:
        self._motor = motor

    def __enter__(self) -> Self:
        self._conexion = self._motor.connect()
        self._transaccion = self._conexion.begin()
        self.notificaciones = RepositorioNotificacionesSql(self._conexion)
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        try:
            if tipo is None:
                self._transaccion.commit()
            else:
                self._transaccion.rollback()
        finally:
            self._conexion.close()
