"""Adaptadores de Postgres para las deudas (SQLAlchemy Core sobre psycopg).

El titular y el código de pago son datos personales: se cifran con AES-256-GCM con el id de la
deuda como contexto. Vincular el documento choca con los índices únicos del espacio si ese archivo
o esa clave de negocio ya respaldan otra deuda: la base es la última barrera contra duplicados.
"""

from datetime import date
from types import TracebackType
from typing import Any, Self
from uuid import UUID

from sqlalchemy import Connection, Engine, Row, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.exc import IntegrityError

from app.acceso.infraestructura.cifrado import CifradorDatos
from app.acceso.infraestructura.persistencia import RegistroAuditoriaSql
from app.categorias.infraestructura.persistencia import RepositorioCategoriasSql
from app.deudas.dominio.errores import DocumentoNoRegistrable
from app.deudas.dominio.modelos import Cuota, Deuda, EstadoDeuda, LugarPago, MotivoEspera
from app.documentos.dominio.modelos import TipoDocumento
from app.documentos.infraestructura.persistencia import (
    RepositorioBloqueosSql,
    RepositorioCuentasSql,
    RepositorioDocumentosSql,
)
from app.notificaciones.infraestructura.persistencia import RepositorioNotificacionesSql
from app.reglas.dominio.titulares import Documento, TipoDocumentoTitular
from app.reglas.infraestructura.persistencia import RepositorioReglasSql

COLUMNAS = """
    id, gerente_id, registrada_por, documento_id, concepto, categoria_id, tipo_documento,
    lugares_pago, titular_cifrado, titular_tipo_documento, titular_documento_cifrado,
    codigo_pago_cifrado, estado, motivos_autorizacion, revision_pendiente, campos_corregidos,
    decidida_por, decidida_en, motivo_decision, creado_en
"""
DOCUMENTO_REPETIDO = {
    "uq_deuda_documento_id",
    "uq_documento_deuda_deuda_id",
    "uq_documento_deuda_archivo_registrado",
    "uq_documento_deuda_clave_registrada",
}


def contexto(campo: str, deuda_id: UUID) -> str:
    return f"deuda.{campo}:{deuda_id}"


class RepositorioDeudasSql:
    def __init__(self, conexion: Connection, cifrador: CifradorDatos) -> None:
        self._conexion = conexion
        self._cifrador = cifrador

    def _descifrar(self, valor: bytes | None, campo: str, deuda_id: UUID) -> str | None:
        return self._cifrador.descifrar(valor, contexto(campo, deuda_id)) if valor else None

    def _cifrar(self, valor: str | None, campo: str, deuda_id: UUID) -> bytes | None:
        return self._cifrador.cifrar(valor, contexto(campo, deuda_id)) if valor else None

    def _cuotas(self, ids: list[UUID]) -> dict[UUID, list[Cuota]]:
        if not ids:
            return {}
        sentencia = text(
            "SELECT deuda_id, numero, vence_el, importe FROM cuota_deuda"
            " WHERE deuda_id IN :ids ORDER BY deuda_id, numero"
        ).bindparams(bindparam("ids", expanding=True))
        cuotas: dict[UUID, list[Cuota]] = {}
        for fila in self._conexion.execute(sentencia, {"ids": ids}):
            cuotas.setdefault(fila.deuda_id, []).append(
                Cuota(fila.numero, fila.vence_el, fila.importe)
            )
        return cuotas

    def _deudas(self, filas: list[Row[Any]]) -> list[Deuda]:
        cuotas = self._cuotas([fila.id for fila in filas])
        deudas = []
        for fila in filas:
            numero = self._descifrar(fila.titular_documento_cifrado, "titular_documento", fila.id)
            deudas.append(
                Deuda(
                    id=fila.id,
                    gerente_id=fila.gerente_id,
                    registrada_por=fila.registrada_por,
                    documento_id=fila.documento_id,
                    concepto=fila.concepto,
                    categoria_id=fila.categoria_id,
                    tipo_documento=TipoDocumento(fila.tipo_documento),
                    cuotas=tuple(cuotas.get(fila.id, [])),
                    lugares_pago=tuple(LugarPago(lugar) for lugar in fila.lugares_pago),
                    titular_nombre=self._descifrar(fila.titular_cifrado, "titular", fila.id),
                    titular_documento=Documento(
                        TipoDocumentoTitular(fila.titular_tipo_documento), numero
                    )
                    if numero and fila.titular_tipo_documento
                    else None,
                    codigo_pago=self._descifrar(fila.codigo_pago_cifrado, "codigo_pago", fila.id),
                    estado=EstadoDeuda(fila.estado),
                    creado_en=fila.creado_en,
                    motivos=tuple(MotivoEspera(m) for m in fila.motivos_autorizacion),
                    revision_pendiente=fila.revision_pendiente,
                    campos_corregidos=tuple(fila.campos_corregidos),
                    decidida_por=fila.decidida_por,
                    decidida_en=fila.decidida_en,
                    motivo_decision=fila.motivo_decision,
                )
            )
        return deudas

    def agregar(self, deuda: Deuda) -> None:
        sentencia = text(
            f"INSERT INTO deuda ({COLUMNAS}, importe, vence_el) VALUES (:id, :gerente_id,"
            " :registrada_por, :documento_id, :concepto, :categoria_id, :tipo_documento,"
            " :lugares_pago, :titular, :titular_tipo_documento, :titular_documento, :codigo_pago,"
            " :estado, :motivos, :revision_pendiente, :corregidos, NULL, NULL, NULL, :creado_en,"
            " :importe, :vence_el)"
        ).bindparams(
            bindparam("lugares_pago", type_=ARRAY(TEXT)),
            bindparam("motivos", type_=ARRAY(TEXT)),
            bindparam("corregidos", type_=ARRAY(TEXT)),
        )
        documento = deuda.titular_documento
        try:
            # Un savepoint: si choca con la unicidad, la transacción sigue utilizable.
            with self._conexion.begin_nested():
                self._conexion.execute(
                    sentencia,
                    {
                        "id": deuda.id,
                        "gerente_id": deuda.gerente_id,
                        "registrada_por": deuda.registrada_por,
                        "documento_id": deuda.documento_id,
                        "concepto": deuda.concepto,
                        "categoria_id": deuda.categoria_id,
                        "tipo_documento": deuda.tipo_documento.value,
                        "lugares_pago": [lugar.value for lugar in deuda.lugares_pago],
                        "titular": self._cifrar(deuda.titular_nombre, "titular", deuda.id),
                        "titular_tipo_documento": documento.tipo.value if documento else None,
                        "titular_documento": self._cifrar(
                            documento.numero if documento else None, "titular_documento", deuda.id
                        ),
                        "codigo_pago": self._cifrar(deuda.codigo_pago, "codigo_pago", deuda.id),
                        "estado": deuda.estado.value,
                        "motivos": [m.value for m in deuda.motivos],
                        "revision_pendiente": deuda.revision_pendiente,
                        "corregidos": list(deuda.campos_corregidos),
                        "creado_en": deuda.creado_en,
                        "importe": deuda.importe,
                        "vence_el": deuda.vence_el,
                    },
                )
                self._conexion.execute(
                    text(
                        "INSERT INTO cuota_deuda (deuda_id, numero, vence_el, importe)"
                        " VALUES (:deuda_id, :numero, :vence_el, :importe)"
                    ),
                    [
                        {
                            "deuda_id": deuda.id,
                            "numero": c.numero,
                            "vence_el": c.vence_el,
                            "importe": c.importe,
                        }
                        for c in deuda.cuotas
                    ],
                )
                self._conexion.execute(
                    text(
                        "UPDATE documento_deuda SET deuda_id = :deuda_id WHERE id = :documento_id"
                    ),
                    {"deuda_id": deuda.id, "documento_id": deuda.documento_id},
                )
        except IntegrityError as error:
            diagnostico = getattr(error.orig, "diag", None)
            if getattr(diagnostico, "constraint_name", None) in DOCUMENTO_REPETIDO:
                raise DocumentoNoRegistrable("DOCUMENTO_YA_USADO") from error
            raise

    def por_id(self, deuda_id: UUID, *, bloquear: bool = False) -> Deuda | None:
        cerrojo = " FOR UPDATE" if bloquear else ""
        filas = self._conexion.execute(
            text(f"SELECT {COLUMNAS} FROM deuda WHERE id = :id{cerrojo}"), {"id": deuda_id}
        ).all()
        deudas = self._deudas(list(filas))
        return deudas[0] if deudas else None

    def guardar(self, deuda: Deuda) -> None:
        self._conexion.execute(
            text(
                "UPDATE deuda SET estado = :estado, revision_pendiente = :revision_pendiente,"
                " decidida_por = :decidida_por, decidida_en = :decidida_en,"
                " motivo_decision = :motivo_decision WHERE id = :id"
            ),
            {
                "id": deuda.id,
                "estado": deuda.estado.value,
                "revision_pendiente": deuda.revision_pendiente,
                "decidida_por": deuda.decidida_por,
                "decidida_en": deuda.decidida_en,
                "motivo_decision": deuda.motivo_decision,
            },
        )

    def del_espacio(self, gerente_id: UUID, *, solo_pendientes: bool) -> list[Deuda]:
        filtro = " AND (estado = 'por_autorizar' OR revision_pendiente)" if solo_pendientes else ""
        filas = self._conexion.execute(
            text(
                f"SELECT {COLUMNAS} FROM deuda WHERE gerente_id = :gerente_id{filtro}"
                " ORDER BY estado <> 'por_autorizar', creado_en DESC LIMIT 200"
            ),
            {"gerente_id": gerente_id},
        ).all()
        return self._deudas(list(filas))

    def registradas_por(self, usuario_id: UUID) -> list[Deuda]:
        filas = self._conexion.execute(
            text(
                f"SELECT {COLUMNAS} FROM deuda WHERE registrada_por = :usuario_id"
                " ORDER BY creado_en DESC LIMIT 200"
            ),
            {"usuario_id": usuario_id},
        ).all()
        return self._deudas(list(filas))

    def con_vencimientos_entre(
        self, gerente_id: UUID, desde: date, hasta: date, *, registrada_por: UUID | None
    ) -> list[Deuda]:
        filtro = " AND registrada_por = :registrada_por" if registrada_por else ""
        filas = self._conexion.execute(
            text(
                f"SELECT {COLUMNAS} FROM deuda WHERE gerente_id = :gerente_id{filtro}"
                " AND estado IN ('por_autorizar', 'registrada') AND EXISTS ("
                " SELECT 1 FROM cuota_deuda WHERE cuota_deuda.deuda_id = deuda.id"
                " AND cuota_deuda.vence_el BETWEEN :desde AND :hasta)"
                " ORDER BY creado_en LIMIT 500"
            ),
            {
                "gerente_id": gerente_id,
                "registrada_por": registrada_por,
                "desde": desde,
                "hasta": hasta,
            },
        ).all()
        return self._deudas(list(filas))


class UnidadDeudasSql:
    def __init__(self, motor: Engine, cifrador: CifradorDatos) -> None:
        self._motor = motor
        self._cifrador = cifrador

    def __enter__(self) -> Self:
        self._conexion = self._motor.connect()
        self._transaccion = self._conexion.begin()
        self.deudas = RepositorioDeudasSql(self._conexion, self._cifrador)
        self.documentos = RepositorioDocumentosSql(self._conexion, self._cifrador)
        self.categorias = RepositorioCategoriasSql(self._conexion)
        self.reglas = RepositorioReglasSql(self._conexion, self._cifrador)
        self.bloqueos = RepositorioBloqueosSql(self._conexion)
        self.cuentas = RepositorioCuentasSql(self._conexion, self._cifrador)
        self.notificaciones = RepositorioNotificacionesSql(self._conexion)
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
