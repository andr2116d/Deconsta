"""Adaptadores de Postgres para las reglas de autorización (SQLAlchemy Core sobre psycopg).

Nombre y documento de cada titular son datos personales de terceros: se cifran con AES-256-GCM
(el id de la fila va como contexto) y se buscan por huellas HMAC con prefijo propio, distintas de
las de las cuentas.
"""

from decimal import Decimal
from types import TracebackType
from typing import Any, Self
from uuid import UUID

from sqlalchemy import Connection, Engine, Row, text
from sqlalchemy.exc import IntegrityError

from app.acceso.dominio.cuenta import FichaPersonal
from app.acceso.infraestructura.cifrado import CifradorDatos
from app.acceso.infraestructura.persistencia import RegistroAuditoriaSql, RepositorioUsuariosSql
from app.reglas.dominio.errores import TitularDuplicado
from app.reglas.dominio.puertos import ReglaAutorizacion
from app.reglas.dominio.titulares import (
    Documento,
    TipoDocumentoTitular,
    TitularAutorizado,
    clave_nombre,
)

COLUMNAS_TITULAR = """
    id, gerente_id, nombre_cifrado, relacion, tipo_documento, numero_documento_cifrado,
    autorizacion_declarada_en, creado_por, creado_en, actualizado_en, quitado_en
"""

DUPLICADOS = {
    "uq_titular_autorizado_nombre": "nombre",
    "uq_titular_autorizado_documento": "numero_documento",
}


def contexto(campo: str, titular_id: UUID) -> str:
    return f"titular_autorizado.{campo}:{titular_id}"


class RepositorioReglasSql:
    def __init__(self, conexion: Connection, cifrador: CifradorDatos) -> None:
        self._conexion = conexion
        self._cifrador = cifrador
        self._usuarios = RepositorioUsuariosSql(conexion, cifrador)

    def bloquear_espacio(self, gerente_id: UUID) -> bool:
        fila = self._conexion.execute(
            text("SELECT id FROM usuario WHERE id = :id AND rol = 'gerente' FOR UPDATE"),
            {"id": gerente_id},
        ).first()
        return fila is not None

    def regla(self, gerente_id: UUID) -> ReglaAutorizacion | None:
        fila = self._conexion.execute(
            text(
                "SELECT limite_importe, actualizado_en FROM regla_autorizacion"
                " WHERE gerente_id = :gerente_id"
            ),
            {"gerente_id": gerente_id},
        ).first()
        return ReglaAutorizacion(fila.limite_importe, fila.actualizado_en) if fila else None

    def guardar_limite(
        self, gerente_id: UUID, limite: Decimal | None, actualizado_por: UUID
    ) -> ReglaAutorizacion:
        fila = self._conexion.execute(
            text(
                "INSERT INTO regla_autorizacion (gerente_id, limite_importe, actualizado_por)"
                " VALUES (:gerente_id, :limite, :actualizado_por)"
                " ON CONFLICT (gerente_id) DO UPDATE SET limite_importe = EXCLUDED.limite_importe,"
                " actualizado_por = EXCLUDED.actualizado_por"
                " RETURNING limite_importe, actualizado_en"
            ),
            {"gerente_id": gerente_id, "limite": limite, "actualizado_por": actualizado_por},
        ).one()
        return ReglaAutorizacion(fila.limite_importe, fila.actualizado_en)

    def _titular(self, fila: Row[Any]) -> TitularAutorizado:
        documento = None
        if fila.tipo_documento:
            numero = self._cifrador.descifrar(
                fila.numero_documento_cifrado, contexto("numero_documento", fila.id)
            )
            documento = Documento(TipoDocumentoTitular(fila.tipo_documento), numero)
        return TitularAutorizado(
            id=fila.id,
            gerente_id=fila.gerente_id,
            nombre=self._cifrador.descifrar(fila.nombre_cifrado, contexto("nombre", fila.id)),
            documento=documento,
            relacion=fila.relacion,
            autorizacion_declarada_en=fila.autorizacion_declarada_en,
            creado_por=fila.creado_por,
            creado_en=fila.creado_en,
            actualizado_en=fila.actualizado_en,
            quitado_en=fila.quitado_en,
        )

    def titulares(self, gerente_id: UUID) -> list[TitularAutorizado]:
        filas = self._conexion.execute(
            text(
                f"SELECT {COLUMNAS_TITULAR} FROM titular_autorizado"
                " WHERE gerente_id = :gerente_id AND quitado_en IS NULL"
            ),
            {"gerente_id": gerente_id},
        ).all()
        # Los nombres están cifrados: se ordenan después de descifrarlos.
        return sorted((self._titular(f) for f in filas), key=lambda t: clave_nombre(t.nombre))

    def titular(self, gerente_id: UUID, titular_id: UUID) -> TitularAutorizado | None:
        fila = self._conexion.execute(
            text(
                f"SELECT {COLUMNAS_TITULAR} FROM titular_autorizado"
                " WHERE id = :id AND gerente_id = :gerente_id AND quitado_en IS NULL"
            ),
            {"id": titular_id, "gerente_id": gerente_id},
        ).first()
        return self._titular(fila) if fila else None

    def _huella_nombre(self, nombre: str) -> bytes:
        return self._cifrador.huella(f"titular.nombre:{clave_nombre(nombre)}")

    def _ejecutar(self, sql: str, parametros: dict[str, Any]) -> None:
        # Un punto de guardado: si choca con la unicidad, la transacción sigue utilizable.
        try:
            with self._conexion.begin_nested():
                self._conexion.execute(text(sql), parametros)
        except IntegrityError as error:
            nombre = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if nombre in DUPLICADOS:
                raise TitularDuplicado(DUPLICADOS[nombre]) from error
            raise

    def agregar_titular(self, titular: TitularAutorizado) -> None:
        documento = titular.documento
        self._ejecutar(
            "INSERT INTO titular_autorizado (id, gerente_id, nombre_cifrado, nombre_huella,"
            " relacion, tipo_documento, numero_documento_cifrado, numero_documento_huella,"
            " autorizacion_declarada_en, creado_por, creado_en, actualizado_en)"
            " VALUES (:id, :gerente_id, :nombre, :nombre_huella, :relacion, :tipo_documento,"
            " :numero_documento, :numero_documento_huella, :autorizacion, :creado_por,"
            " :creado_en, :creado_en)",
            {
                "id": titular.id,
                "gerente_id": titular.gerente_id,
                "nombre": self._cifrador.cifrar(titular.nombre, contexto("nombre", titular.id)),
                "nombre_huella": self._huella_nombre(titular.nombre),
                "relacion": titular.relacion,
                "tipo_documento": documento.tipo.value if documento else None,
                "numero_documento": (
                    self._cifrador.cifrar(
                        documento.numero, contexto("numero_documento", titular.id)
                    )
                    if documento
                    else None
                ),
                "numero_documento_huella": (
                    self._cifrador.huella(
                        f"titular.documento:{documento.tipo.value}:{documento.numero}"
                    )
                    if documento
                    else None
                ),
                "autorizacion": titular.autorizacion_declarada_en,
                "creado_por": titular.creado_por,
                "creado_en": titular.creado_en,
            },
        )

    def guardar_titular(self, titular: TitularAutorizado) -> None:
        self._ejecutar(
            "UPDATE titular_autorizado SET nombre_cifrado = :nombre,"
            " nombre_huella = :nombre_huella, relacion = :relacion, quitado_en = :quitado_en"
            " WHERE id = :id",
            {
                "id": titular.id,
                "nombre": self._cifrador.cifrar(titular.nombre, contexto("nombre", titular.id)),
                "nombre_huella": self._huella_nombre(titular.nombre),
                "relacion": titular.relacion,
                "quitado_en": titular.quitado_en,
            },
        )

    def ficha_gerente(self, gerente_id: UUID) -> FichaPersonal | None:
        return self._usuarios.ficha(gerente_id)


class UnidadReglasSql:
    def __init__(self, motor: Engine, cifrador: CifradorDatos) -> None:
        self._motor = motor
        self._cifrador = cifrador

    def __enter__(self) -> Self:
        self._conexion = self._motor.connect()
        self._transaccion = self._conexion.begin()
        self.reglas = RepositorioReglasSql(self._conexion, self._cifrador)
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
