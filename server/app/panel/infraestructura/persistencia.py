"""Consultas de Postgres para el panel. Solo lee y no toca columnas cifradas."""

from datetime import date
from decimal import Decimal
from types import TracebackType
from typing import Any, Self
from uuid import UUID

from sqlalchemy import Connection, Engine, Row, text

from app.acceso.infraestructura.cifrado import CifradorDatos
from app.deudas.dominio.modelos import LugarPago
from app.deudas.infraestructura.persistencia import PAGO_VIGENTE
from app.documentos.infraestructura.persistencia import RepositorioCuentasSql
from app.panel.dominio.modelos import CuotaProxima, Pendiente, TipoPendiente

CUOTAS = "FROM cuota_deuda c JOIN deuda d ON d.id = c.deuda_id"
# La cuota aún no tiene un pago vigente.
SIN_PAGO = (
    "NOT EXISTS (SELECT 1 FROM pago WHERE pago.deuda_id = c.deuda_id AND pago.cuota = c.numero"
    f" AND {PAGO_VIGENTE})"
)
# Las cuotas de las deudas registradas del espacio que faltan pagar.
POR_PAGAR = f"d.gerente_id = :gerente_id AND d.estado = 'registrada' AND {SIN_PAGO}"
COLUMNAS_CUOTA = """
    c.deuda_id, d.concepto, d.categoria_id, c.numero AS cuota,
    (SELECT count(*) FROM cuota_deuda t WHERE t.deuda_id = d.id) AS cuotas,
    c.importe, c.vence_el, d.lugares_pago,
    pp.id AS pedido_id, pp.asistente_id AS pedido_a, pp.nota
"""
PEDIDO = """
    LEFT JOIN pedido_pago pp ON pp.deuda_id = c.deuda_id AND pp.cuota = c.numero
        AND pp.retirado_en IS NULL
"""


def _cuota(fila: Row[Any]) -> CuotaProxima:
    return CuotaProxima(
        deuda_id=fila.deuda_id,
        concepto=fila.concepto,
        categoria_id=fila.categoria_id,
        cuota=fila.cuota,
        cuotas=fila.cuotas,
        importe=fila.importe,
        vence_el=fila.vence_el,
        lugares_pago=tuple(LugarPago(lugar) for lugar in fila.lugares_pago),
        pedido_id=fila.pedido_id,
        pedido_a=fila.pedido_a,
        nota=fila.nota,
    )


class RepositorioPanelSql:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    def por_pagar(self, gerente_id: UUID, hoy: date) -> tuple[Decimal, int, int]:
        fila = self._conexion.execute(
            text(
                "SELECT coalesce(sum(c.importe), 0) AS importe, count(*) AS cuotas,"
                f" count(*) FILTER (WHERE c.vence_el < :hoy) AS vencidas {CUOTAS} WHERE {POR_PAGAR}"
            ),
            {"gerente_id": gerente_id, "hoy": hoy},
        ).one()
        return fila.importe, fila.cuotas, fila.vencidas

    def pagado_entre(self, gerente_id: UUID, desde: date, hasta: date) -> tuple[Decimal, int]:
        fila = self._conexion.execute(
            text(
                "SELECT coalesce(sum(importe), 0) AS importe, count(*) AS pagos FROM pago"
                f" WHERE gerente_id = :gerente_id AND {PAGO_VIGENTE}"
                " AND pagado_el BETWEEN :desde AND :hasta"
            ),
            {"gerente_id": gerente_id, "desde": desde, "hasta": hasta},
        ).one()
        return fila.importe, fila.pagos

    def pendientes(self, gerente_id: UUID) -> list[Pendiente]:
        filas = self._conexion.execute(
            text(
                # Deudas que esperan su autorización o su visto bueno.
                "SELECT CASE WHEN d.estado = 'por_autorizar' THEN 'autorizar_deuda'"
                " ELSE 'revisar_deuda' END AS tipo, d.id, d.id AS deuda_id, d.concepto,"
                " d.importe, d.vence_el, d.registrada_por AS por, d.creado_en AS desde"
                " FROM deuda d WHERE d.gerente_id = :gerente_id"
                " AND (d.estado = 'por_autorizar' OR d.revision_pendiente)"
                " UNION ALL"
                " SELECT 'verificar_pago', p.id, p.deuda_id, d.concepto, p.importe, c.vence_el,"
                " p.registrado_por, p.registrado_en FROM pago p"
                " JOIN deuda d ON d.id = p.deuda_id"
                " JOIN cuota_deuda c ON c.deuda_id = p.deuda_id AND c.numero = p.cuota"
                " WHERE p.gerente_id = :gerente_id AND p.estado = 'por_verificar'"
                " UNION ALL"
                " SELECT 'aprobar_mora', m.id, m.deuda_id, d.concepto, m.importe, c.vence_el,"
                " m.declarada_por, m.declarada_en FROM mora m"
                " JOIN deuda d ON d.id = m.deuda_id"
                " JOIN cuota_deuda c ON c.deuda_id = m.deuda_id AND c.numero = m.cuota"
                " WHERE m.gerente_id = :gerente_id AND m.estado = 'por_aprobar'"
                " LIMIT 100"
            ),
            {"gerente_id": gerente_id},
        ).all()
        return [
            Pendiente(
                TipoPendiente(f.tipo),
                f.id,
                f.deuda_id,
                f.concepto,
                f.importe,
                f.vence_el,
                f.por,
                f.desde,
            )
            for f in filas
        ]

    def proximas(self, gerente_id: UUID, limite: int) -> list[CuotaProxima]:
        filas = self._conexion.execute(
            text(
                f"SELECT {COLUMNAS_CUOTA} {CUOTAS} {PEDIDO} WHERE {POR_PAGAR}"
                " ORDER BY c.vence_el, d.creado_en LIMIT :limite"
            ),
            {"gerente_id": gerente_id, "limite": limite},
        ).all()
        return [_cuota(f) for f in filas]

    def pedidas_a(self, asistente_id: UUID) -> list[CuotaProxima]:
        filas = self._conexion.execute(
            text(
                f"SELECT {COLUMNAS_CUOTA} FROM pedido_pago pp"
                " JOIN cuota_deuda c ON c.deuda_id = pp.deuda_id AND c.numero = pp.cuota"
                " JOIN deuda d ON d.id = c.deuda_id"
                " WHERE pp.asistente_id = :asistente_id AND pp.retirado_en IS NULL"
                f" AND d.estado = 'registrada' AND {SIN_PAGO} ORDER BY pp.pedido_en"
            ),
            {"asistente_id": asistente_id},
        ).all()
        return [_cuota(f) for f in filas]

    def devueltas(self, gerente_id: UUID) -> int:
        fila = self._conexion.execute(
            text(
                f"SELECT count(*) AS cuotas {CUOTAS} WHERE {POR_PAGAR}"
                " AND EXISTS (SELECT 1 FROM pago WHERE pago.deuda_id = c.deuda_id"
                " AND pago.cuota = c.numero"
                " AND pago.estado = 'devuelto')"
            ),
            {"gerente_id": gerente_id},
        ).one()
        return int(fila.cuotas)

    def en_espera_de(self, asistente_id: UUID) -> int:
        fila = self._conexion.execute(
            text(
                "SELECT (SELECT count(*) FROM deuda WHERE registrada_por = :id"
                " AND estado = 'por_autorizar')"
                " + (SELECT count(*) FROM pago WHERE registrado_por = :id"
                " AND estado = 'por_verificar')"
                " + (SELECT count(*) FROM mora WHERE declarada_por = :id"
                " AND estado = 'por_aprobar') AS total"
            ),
            {"id": asistente_id},
        ).one()
        return int(fila.total)

    def limite(self, gerente_id: UUID) -> Decimal | None:
        fila = self._conexion.execute(
            text("SELECT limite_importe FROM regla_autorizacion WHERE gerente_id = :gerente_id"),
            {"gerente_id": gerente_id},
        ).first()
        return fila.limite_importe if fila else None


class UnidadPanelSql:
    def __init__(self, motor: Engine, cifrador: CifradorDatos) -> None:
        self._motor = motor
        self._cifrador = cifrador

    def __enter__(self) -> Self:
        self._conexion = self._motor.connect()
        self._transaccion = self._conexion.begin()
        self.panel = RepositorioPanelSql(self._conexion)
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
