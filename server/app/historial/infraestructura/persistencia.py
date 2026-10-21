"""Consultas de Postgres para el historial. Solo lee: deudas, cuotas, pagos, moras y la auditoría.
No toca columnas cifradas: el titular y el código de pago no forman parte del historial."""

from collections.abc import Iterable
from datetime import datetime
from types import TracebackType
from typing import Any, Self
from uuid import UUID

from sqlalchemy import Connection, Engine, bindparam, text

from app.acceso.infraestructura.cifrado import CifradorDatos
from app.deudas.dominio.modelos import EstadoDeuda, EstadoPago, LugarPago
from app.documentos.dominio.modelos import TipoDocumento
from app.documentos.infraestructura.persistencia import RepositorioCuentasSql
from app.historial.dominio.modelos import (
    ESTADOS_DEUDA,
    ESTADOS_PAGO,
    CuotaHistorial,
    DeudaHistorial,
    EstadoFiltro,
    Evento,
    Filtros,
    MoraHistorial,
    PagoHistorial,
    Posicion,
)
from app.pagos.dominio.modelos import EstadoMora

# Lo que cuenta en la línea de tiempo de una deuda.
ACCIONES = (
    "DEUDA_REGISTRADA",
    "DEUDA_AUTORIZADA",
    "DEUDA_RECHAZADA",
    "DEUDA_REVISADA",
    "DEUDA_ANULADA",
    "PAGO_REGISTRADO",
    "PAGO_CONFIRMADO",
    "PAGO_DEVUELTO",
    "MORA_DECLARADA",
    "MORA_APROBADA",
    "MORA_RECHAZADA",
    "PAGO_PEDIDO",
    "PEDIDO_RETIRADO",
)


def _patron(texto: str) -> str:
    """Un LIKE literal: el % y el _ que escriba la persona no son comodines."""
    escapado = texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escapado}%"


class RepositorioHistorialSql:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    def buscar(
        self,
        gerente_id: UUID,
        filtros: Filtros,
        inicio: datetime,
        fin: datetime,
        despues: Posicion | None,
        limite: int,
    ) -> list[DeudaHistorial]:
        condiciones = [
            "d.gerente_id = :gerente_id",
            "(d.creado_en >= :inicio AND d.creado_en < :fin OR EXISTS (SELECT 1 FROM auditoria a"
            " WHERE a.detalle ? 'deuda_id' AND a.detalle ->> 'deuda_id' = d.id::text"
            " AND a.ocurrido_en >= :inicio AND a.ocurrido_en < :fin))",
        ]
        parametros: dict[str, Any] = {
            "gerente_id": gerente_id,
            "inicio": inicio,
            "fin": fin,
            "limite": limite,
        }
        estado = filtros.estado
        if estado in ESTADOS_DEUDA:
            condiciones.append("d.estado = :estado")
            parametros["estado"] = estado.value
        elif estado in ESTADOS_PAGO:
            assert estado is not None
            condiciones.append(
                "EXISTS (SELECT 1 FROM pago p WHERE p.deuda_id = d.id AND p.estado = :estado)"
            )
            parametros["estado"] = estado.value
        elif estado is EstadoFiltro.MORA:
            condiciones.append("EXISTS (SELECT 1 FROM mora m WHERE m.deuda_id = d.id)")
        if filtros.categoria_id:
            condiciones.append("d.categoria_id = :categoria_id")
            parametros["categoria_id"] = filtros.categoria_id
        if filtros.registrada_por:
            condiciones.append("d.registrada_por = :registrada_por")
            parametros["registrada_por"] = filtros.registrada_por
        if filtros.pagado_por:
            condiciones.append(
                "EXISTS (SELECT 1 FROM pago p WHERE p.deuda_id = d.id"
                " AND p.registrado_por = :pagado_por)"
            )
            parametros["pagado_por"] = filtros.pagado_por
        if filtros.lugar_pago:
            condiciones.append(":lugar_pago = ANY(d.lugares_pago)")
            parametros["lugar_pago"] = filtros.lugar_pago.value
        if filtros.texto:
            condiciones.append("d.concepto ILIKE :texto ESCAPE '\\'")
            parametros["texto"] = _patron(filtros.texto)
        if filtros.de_la_cuenta:
            condiciones.append(
                "(d.registrada_por = :cuenta OR EXISTS (SELECT 1 FROM pago p"
                " WHERE p.deuda_id = d.id AND p.registrado_por = :cuenta))"
            )
            parametros["cuenta"] = filtros.de_la_cuenta
        if despues:
            condiciones.append("(d.creado_en, d.id) < (:despues_en, :despues_id)")
            parametros["despues_en"] = despues.creado_en
            parametros["despues_id"] = despues.id
        filas = self._conexion.execute(
            text(
                "SELECT d.id, d.concepto, d.categoria_id, d.tipo_documento, d.lugares_pago,"
                " d.importe, d.estado, d.revision_pendiente, d.motivos_autorizacion,"
                " d.registrada_por, d.creado_en, d.motivo_decision FROM deuda d"
                f" WHERE {' AND '.join(condiciones)}"
                " ORDER BY d.creado_en DESC, d.id DESC LIMIT :limite"
            ),
            parametros,
        ).all()
        ids = [fila.id for fila in filas]
        cuotas = self._cuotas(ids)
        pagos = self._pagos(ids)
        moras = self._moras(ids)
        eventos = self._eventos(ids, pagos, moras)
        return [
            DeudaHistorial(
                id=fila.id,
                concepto=fila.concepto,
                categoria_id=fila.categoria_id,
                tipo_documento=TipoDocumento(fila.tipo_documento),
                lugares_pago=tuple(LugarPago(lugar) for lugar in fila.lugares_pago),
                importe=fila.importe,
                estado=EstadoDeuda(fila.estado),
                revision_pendiente=fila.revision_pendiente,
                motivos=tuple(fila.motivos_autorizacion),
                registrada_por=fila.registrada_por,
                creado_en=fila.creado_en,
                motivo_decision=fila.motivo_decision,
                cuotas=tuple(cuotas.get(fila.id, [])),
                pagos=tuple(pagos.get(fila.id, [])),
                moras=tuple(moras.get(fila.id, [])),
                eventos=tuple(eventos.get(fila.id, [])),
            )
            for fila in filas
        ]

    def _de(self, sentencia: str, ids: list[UUID]) -> list[Any]:
        if not ids:
            return []
        consulta = text(sentencia).bindparams(bindparam("ids", expanding=True))
        return list(self._conexion.execute(consulta, {"ids": ids}).all())

    def _cuotas(self, ids: list[UUID]) -> dict[UUID, list[CuotaHistorial]]:
        cuotas: dict[UUID, list[CuotaHistorial]] = {}
        for fila in self._de(
            "SELECT deuda_id, numero, vence_el, importe FROM cuota_deuda"
            " WHERE deuda_id IN :ids ORDER BY deuda_id, numero",
            ids,
        ):
            cuotas.setdefault(fila.deuda_id, []).append(
                CuotaHistorial(fila.numero, fila.vence_el, fila.importe)
            )
        return cuotas

    def _pagos(self, ids: list[UUID]) -> dict[UUID, list[PagoHistorial]]:
        pagos: dict[UUID, list[PagoHistorial]] = {}
        for fila in self._de(
            "SELECT id, deuda_id, cuota, importe, comision, mora, lugar_pago, pagado_el, estado,"
            " confianza, registrado_por, registrado_en, decidido_en, motivo_decision FROM pago"
            " WHERE deuda_id IN :ids ORDER BY registrado_en",
            ids,
        ):
            pagos.setdefault(fila.deuda_id, []).append(
                PagoHistorial(
                    id=fila.id,
                    cuota=fila.cuota,
                    importe=fila.importe,
                    comision=fila.comision,
                    mora=fila.mora,
                    lugar_pago=LugarPago(fila.lugar_pago) if fila.lugar_pago else None,
                    pagado_el=fila.pagado_el,
                    estado=EstadoPago(fila.estado),
                    confianza=fila.confianza,
                    registrado_por=fila.registrado_por,
                    registrado_en=fila.registrado_en,
                    decidido_en=fila.decidido_en,
                    motivo_decision=fila.motivo_decision,
                )
            )
        return pagos

    def _moras(self, ids: list[UUID]) -> dict[UUID, list[MoraHistorial]]:
        moras: dict[UUID, list[MoraHistorial]] = {}
        for fila in self._de(
            "SELECT id, deuda_id, cuota, importe, estado, declarada_por, declarada_en,"
            " decidida_en, motivo_decision FROM mora WHERE deuda_id IN :ids"
            " ORDER BY declarada_en",
            ids,
        ):
            moras.setdefault(fila.deuda_id, []).append(
                MoraHistorial(
                    id=fila.id,
                    cuota=fila.cuota,
                    importe=fila.importe,
                    estado=EstadoMora(fila.estado),
                    declarada_por=fila.declarada_por,
                    declarada_en=fila.declarada_en,
                    decidida_en=fila.decidida_en,
                    motivo_decision=fila.motivo_decision,
                )
            )
        return moras

    def _eventos(
        self,
        ids: list[UUID],
        pagos: dict[UUID, list[PagoHistorial]],
        moras: dict[UUID, list[MoraHistorial]],
    ) -> dict[UUID, list[Evento]]:
        """La cuota de cada evento sale del pago o de la mora cuando la auditoría no la guarda."""
        if not ids:
            return {}
        cuota_de = {str(p.id): p.cuota for lista in pagos.values() for p in lista}
        cuota_de.update({str(m.id): m.cuota for lista in moras.values() for m in lista})
        consulta = text(
            "SELECT detalle ->> 'deuda_id' AS deuda_id, accion, ocurrido_en, actor_id, motivo,"
            " detalle ->> 'cuota' AS cuota,"
            " coalesce(detalle ->> 'pago_id', detalle ->> 'mora_id') AS referencia"
            " FROM auditoria WHERE detalle ? 'deuda_id' AND detalle ->> 'deuda_id' IN :ids"
            " AND accion IN :acciones ORDER BY ocurrido_en, id"
        ).bindparams(bindparam("ids", expanding=True), bindparam("acciones", expanding=True))
        eventos: dict[UUID, list[Evento]] = {}
        for fila in self._conexion.execute(
            consulta, {"ids": [str(i) for i in ids], "acciones": list(ACCIONES)}
        ):
            cuota = int(fila.cuota) if fila.cuota else cuota_de.get(fila.referencia or "")
            eventos.setdefault(UUID(fila.deuda_id), []).append(
                Evento(fila.accion, fila.ocurrido_en, fila.actor_id, fila.motivo, cuota)
            )
        return eventos

    def usuarios(self, ids: Iterable[UUID]) -> dict[UUID, str]:
        filas = self._de("SELECT id, nombre_usuario FROM usuario WHERE id IN :ids", list(ids))
        return {fila.id: fila.nombre_usuario for fila in filas}

    def categorias(self, gerente_id: UUID) -> dict[UUID, str]:
        filas = self._conexion.execute(
            text("SELECT id, nombre FROM categoria WHERE gerente_id = :gerente_id"),
            {"gerente_id": gerente_id},
        ).all()
        return {fila.id: fila.nombre for fila in filas}


class UnidadHistorialSql:
    def __init__(self, motor: Engine, cifrador: CifradorDatos) -> None:
        self._motor = motor
        self._cifrador = cifrador

    def __enter__(self) -> Self:
        self._conexion = self._motor.connect()
        self._transaccion = self._conexion.begin()
        self.historial = RepositorioHistorialSql(self._conexion)
        self.cuentas = RepositorioCuentasSql(self._conexion, self._cifrador)
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        # Solo lee: nada que confirmar.
        try:
            self._transaccion.rollback()
        finally:
            self._conexion.close()
