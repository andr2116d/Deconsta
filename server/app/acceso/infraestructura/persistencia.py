"""Adaptadores de Postgres para los puertos del acceso (SQLAlchemy Core sobre psycopg)."""

import json
from datetime import datetime
from types import TracebackType
from typing import Any, Self
from uuid import UUID

from sqlalchemy import Connection, Engine, Row, text
from sqlalchemy.exc import IntegrityError

from app.acceso.dominio.datos_personales import DatosPersonales
from app.acceso.dominio.errores import DatosDuplicados
from app.acceso.dominio.modelos import EventoAuditoria, Rol, Sesion, Usuario
from app.acceso.infraestructura.cifrado import CifradorDatos

COLUMNAS_USUARIO = """
    id, rol, gerente_id, nombre_usuario, nombres_cifrado, contrasena_hash,
    debe_cambiar_contrasena, contrasena_actualizada_en, ultimo_ingreso_en,
    intentos_fallidos, bloqueada_en
"""

CAMPOS_DUPLICADOS = {
    "uq_usuario_nombre_usuario": ("nombre_usuario", "Ese usuario ya está en uso."),
    "uq_usuario_correo_huella": ("correo", "Ese correo ya pertenece a otra cuenta."),
    "uq_usuario_documento_huella": (
        "numero_documento",
        "Ese documento ya pertenece a otra cuenta.",
    ),
}


def contexto(campo: str, usuario_id: UUID) -> str:
    return f"usuario.{campo}:{usuario_id}"


class RepositorioUsuariosSql:
    def __init__(self, conexion: Connection, cifrador: CifradorDatos) -> None:
        self._conexion = conexion
        self._cifrador = cifrador

    def _usuario(self, fila: Row[Any] | None) -> Usuario | None:
        if fila is None:
            return None
        return Usuario(
            id=fila.id,
            rol=Rol(fila.rol),
            gerente_id=fila.gerente_id,
            nombre_usuario=fila.nombre_usuario,
            nombres=self._cifrador.descifrar(fila.nombres_cifrado, contexto("nombres", fila.id)),
            contrasena_hash=fila.contrasena_hash,
            debe_cambiar_contrasena=fila.debe_cambiar_contrasena,
            contrasena_actualizada_en=fila.contrasena_actualizada_en,
            ultimo_ingreso_en=fila.ultimo_ingreso_en,
            intentos_fallidos=fila.intentos_fallidos,
            bloqueada_en=fila.bloqueada_en,
        )

    def _buscar(self, condicion: str, parametros: dict[str, Any], bloquear: bool) -> Usuario | None:
        sql = f"SELECT {COLUMNAS_USUARIO} FROM usuario WHERE {condicion}"
        if bloquear:
            sql += " FOR UPDATE"
        return self._usuario(self._conexion.execute(text(sql), parametros).one_or_none())

    def por_nombre_usuario(self, nombre_usuario: str, *, bloquear: bool) -> Usuario | None:
        return self._buscar("nombre_usuario = :nombre", {"nombre": nombre_usuario}, bloquear)

    def por_id(self, usuario_id: UUID, *, bloquear: bool) -> Usuario | None:
        return self._buscar("id = :id", {"id": usuario_id}, bloquear)

    def existe_nombre_usuario(self, nombre_usuario: str) -> bool:
        fila = self._conexion.execute(
            text("SELECT 1 FROM usuario WHERE nombre_usuario = :nombre"),
            {"nombre": nombre_usuario},
        ).first()
        return fila is not None

    def guardar(self, usuario: Usuario) -> None:
        self._conexion.execute(
            text(
                """
                UPDATE usuario SET
                    contrasena_hash = :contrasena_hash,
                    debe_cambiar_contrasena = :debe_cambiar_contrasena,
                    contrasena_actualizada_en = :contrasena_actualizada_en,
                    ultimo_ingreso_en = :ultimo_ingreso_en,
                    intentos_fallidos = :intentos_fallidos,
                    bloqueada_en = :bloqueada_en
                WHERE id = :id
                """
            ),
            {
                "id": usuario.id,
                "contrasena_hash": usuario.contrasena_hash,
                "debe_cambiar_contrasena": usuario.debe_cambiar_contrasena,
                "contrasena_actualizada_en": usuario.contrasena_actualizada_en,
                "ultimo_ingreso_en": usuario.ultimo_ingreso_en,
                "intentos_fallidos": usuario.intentos_fallidos,
                "bloqueada_en": usuario.bloqueada_en,
            },
        )

    def agregar(self, usuario: Usuario, datos: DatosPersonales) -> None:
        def cifrar(campo: str, valor: str) -> bytes:
            return self._cifrador.cifrar(valor, contexto(campo, usuario.id))

        documento = f"{datos.tipo_documento.value}:{datos.numero_documento}"
        try:
            self._conexion.execute(
                text(
                    """
                    INSERT INTO usuario (
                        id, rol, gerente_id, nombre_usuario, contrasena_hash,
                        nombres_cifrado, apellidos_cifrado, correo_cifrado, correo_huella,
                        telefono_cifrado, tipo_documento, numero_documento_cifrado,
                        numero_documento_huella, debe_cambiar_contrasena,
                        contrasena_actualizada_en
                    ) VALUES (
                        :id, :rol, :gerente_id, :nombre_usuario, :contrasena_hash,
                        :nombres, :apellidos, :correo, :correo_huella,
                        :telefono, :tipo_documento, :numero_documento,
                        :numero_documento_huella, :debe_cambiar_contrasena,
                        :contrasena_actualizada_en
                    )
                    """
                ),
                {
                    "id": usuario.id,
                    "rol": usuario.rol.value,
                    "gerente_id": usuario.gerente_id,
                    "nombre_usuario": usuario.nombre_usuario,
                    "contrasena_hash": usuario.contrasena_hash,
                    "nombres": cifrar("nombres", datos.nombres),
                    "apellidos": cifrar("apellidos", datos.apellidos),
                    "correo": cifrar("correo", datos.correo),
                    "correo_huella": self._cifrador.huella(datos.correo),
                    "telefono": cifrar("telefono", datos.telefono) if datos.telefono else None,
                    "tipo_documento": datos.tipo_documento.value,
                    "numero_documento": cifrar("numero_documento", datos.numero_documento),
                    "numero_documento_huella": self._cifrador.huella(documento),
                    "debe_cambiar_contrasena": usuario.debe_cambiar_contrasena,
                    "contrasena_actualizada_en": usuario.contrasena_actualizada_en,
                },
            )
        except IntegrityError as error:
            restriccion = getattr(error.orig, "diag", None)
            nombre = getattr(restriccion, "constraint_name", None)
            if nombre in CAMPOS_DUPLICADOS:
                campo, mensaje = CAMPOS_DUPLICADOS[nombre]
                raise DatosDuplicados(campos={campo: mensaje}) from error
            raise


class RepositorioSesionesSql:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    def agregar(self, sesion: Sesion) -> None:
        self._conexion.execute(
            text(
                "INSERT INTO sesion (id, usuario_id, token_huella, creada_en, expira_en)"
                " VALUES (:id, :usuario_id, :token_huella, :creada_en, :expira_en)"
            ),
            {
                "id": sesion.id,
                "usuario_id": sesion.usuario_id,
                "token_huella": sesion.token_huella,
                "creada_en": sesion.creada_en,
                "expira_en": sesion.expira_en,
            },
        )

    def vigente(self, token_huella: bytes, ahora: datetime) -> Sesion | None:
        fila = self._conexion.execute(
            text(
                "SELECT id, usuario_id, token_huella, creada_en, expira_en FROM sesion"
                " WHERE token_huella = :huella AND revocada_en IS NULL AND expira_en > :ahora"
            ),
            {"huella": token_huella, "ahora": ahora},
        ).one_or_none()
        if fila is None:
            return None
        return Sesion(fila.id, fila.usuario_id, fila.token_huella, fila.creada_en, fila.expira_en)

    def revocar(self, sesion_id: UUID, ahora: datetime, motivo: str) -> None:
        self._conexion.execute(
            text(
                "UPDATE sesion SET revocada_en = :ahora, motivo_revocacion = :motivo"
                " WHERE id = :id AND revocada_en IS NULL"
            ),
            {"id": sesion_id, "ahora": ahora, "motivo": motivo},
        )

    def revocar_de_usuario(
        self, usuario_id: UUID, ahora: datetime, motivo: str, *, excepto: UUID | None = None
    ) -> int:
        resultado = self._conexion.execute(
            text(
                "UPDATE sesion SET revocada_en = :ahora, motivo_revocacion = :motivo"
                " WHERE usuario_id = :usuario_id AND revocada_en IS NULL"
                " AND (CAST(:excepto AS uuid) IS NULL OR id <> CAST(:excepto AS uuid))"
            ),
            {"usuario_id": usuario_id, "ahora": ahora, "motivo": motivo, "excepto": excepto},
        )
        return resultado.rowcount


class RegistroAuditoriaSql:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    def registrar(self, evento: EventoAuditoria) -> None:
        self._conexion.execute(
            text(
                "INSERT INTO auditoria (accion, actor_id, cuenta_id, motivo, detalle)"
                " VALUES (:accion, :actor_id, :cuenta_id, :motivo, CAST(:detalle AS jsonb))"
            ),
            {
                "accion": evento.accion.value,
                "actor_id": evento.actor_id,
                "cuenta_id": evento.cuenta_id,
                "motivo": evento.motivo,
                "detalle": json.dumps(evento.detalle),
            },
        )


class UnidadDeTrabajoSql:
    def __init__(self, motor: Engine, cifrador: CifradorDatos) -> None:
        self._motor = motor
        self._cifrador = cifrador

    def __enter__(self) -> Self:
        self._conexion = self._motor.connect()
        self._transaccion = self._conexion.begin()
        self.usuarios = RepositorioUsuariosSql(self._conexion, self._cifrador)
        self.sesiones = RepositorioSesionesSql(self._conexion)
        self.auditoria = RegistroAuditoriaSql(self._conexion)
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
