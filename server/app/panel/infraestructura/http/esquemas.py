from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.acceso.dominio.modelos import Rol
from app.deudas.dominio.modelos import LugarPago
from app.panel.aplicacion.panel import Panel
from app.panel.dominio.modelos import CuotaProxima, Pendiente, TipoPendiente


class PendienteSalida(BaseModel):
    tipo: TipoPendiente
    # El id de la deuda, del pago o de la mora, según el tipo.
    id: UUID
    deuda_id: UUID
    concepto: str
    importe: str
    vence_el: date
    por: str
    desde: datetime

    @classmethod
    def desde_pendiente(cls, p: Pendiente, nombres: dict[UUID, str]) -> "PendienteSalida":
        return cls(
            tipo=p.tipo,
            id=p.id,
            deuda_id=p.deuda_id,
            concepto=p.concepto,
            importe=str(p.importe),
            vence_el=p.vence_el,
            por=nombres.get(p.por, ""),
            desde=p.desde,
        )


class PedidoPanelSalida(BaseModel):
    id: UUID
    asistente_id: UUID
    asistente: str
    nota: str | None


class CuotaPanelSalida(BaseModel):
    deuda_id: UUID
    concepto: str
    categoria_id: UUID | None
    cuota: int
    cuotas: int
    importe: str
    vence_el: date
    lugares_pago: list[LugarPago]
    pedido: PedidoPanelSalida | None

    @classmethod
    def desde(cls, c: CuotaProxima, nombres: dict[UUID, str]) -> "CuotaPanelSalida":
        return cls(
            deuda_id=c.deuda_id,
            concepto=c.concepto,
            categoria_id=c.categoria_id,
            cuota=c.cuota,
            cuotas=c.cuotas,
            importe=str(c.importe),
            vence_el=c.vence_el,
            lugares_pago=list(c.lugares_pago),
            pedido=PedidoPanelSalida(
                id=c.pedido_id,
                asistente_id=c.pedido_a,
                asistente=nombres.get(c.pedido_a, ""),
                nota=c.nota,
            )
            if c.pedido_id and c.pedido_a
            else None,
        )


class ResumenSalida(BaseModel):
    por_pagar: str
    cuotas_por_pagar: int
    vencidas: int
    pagado_mes: str
    pagos_mes: int
    pendientes: list[PendienteSalida]
    proximas: list[CuotaPanelSalida]


class JornadaSalida(BaseModel):
    por_completar: int
    devueltas: int
    en_manos_del_gerente: int
    gerente: str
    siguiente: CuotaPanelSalida | None
    # Sobre este importe, lo que registre espera la autorización; nulo: sin límite.
    limite: str | None


class PanelSalida(BaseModel):
    hoy: date
    rol: Rol
    resumen: ResumenSalida | None
    jornada: JornadaSalida | None

    @classmethod
    def desde(cls, panel: Panel, rol: Rol, gerente_id: UUID) -> "PanelSalida":
        g, a, nombres = panel.gerente, panel.asistente, panel.nombres
        return cls(
            hoy=panel.hoy,
            rol=rol,
            resumen=ResumenSalida(
                por_pagar=str(g.por_pagar),
                cuotas_por_pagar=g.cuotas_por_pagar,
                vencidas=g.vencidas,
                pagado_mes=str(g.pagado_mes),
                pagos_mes=g.pagos_mes,
                pendientes=[PendienteSalida.desde_pendiente(p, nombres) for p in g.pendientes],
                proximas=[CuotaPanelSalida.desde(c, nombres) for c in g.proximas],
            )
            if g
            else None,
            jornada=JornadaSalida(
                por_completar=a.por_completar,
                devueltas=a.devueltas,
                en_manos_del_gerente=a.en_manos_del_gerente,
                gerente=nombres.get(gerente_id, ""),
                siguiente=CuotaPanelSalida.desde(a.siguiente, nombres) if a.siguiente else None,
                limite=str(a.limite) if a.limite is not None else None,
            )
            if a
            else None,
        )
