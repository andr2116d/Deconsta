import base64
import binascii
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.deudas.dominio.modelos import EstadoDeuda, EstadoPago, LugarPago
from app.documentos.dominio.modelos import TipoDocumento
from app.historial.aplicacion.historial import PaginaHistorial
from app.historial.dominio.errores import FiltroInvalido
from app.historial.dominio.modelos import (
    CuotaHistorial,
    DeudaHistorial,
    Evento,
    MoraHistorial,
    PagoHistorial,
    Posicion,
)
from app.pagos.dominio.modelos import EstadoMora


def cifrar_cursor(posicion: Posicion) -> str:
    """Opaco para el cliente: solo lo devuelve tal cual para pedir la página siguiente."""
    crudo = f"{posicion.creado_en.isoformat()}|{posicion.id}".encode()
    return base64.urlsafe_b64encode(crudo).decode().rstrip("=")


def leer_cursor(cursor: str) -> Posicion:
    try:
        crudo = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        en, identificador = crudo.split("|")
        posicion = Posicion(datetime.fromisoformat(en), UUID(identificador))
    except (binascii.Error, UnicodeDecodeError, ValueError) as error:
        mensaje = "La página pedida no es válida. Vuelve a cargar el historial."
        raise FiltroInvalido(mensaje, campos={"cursor": mensaje}) from error
    if posicion.creado_en.tzinfo is None:
        mensaje = "La página pedida no es válida. Vuelve a cargar el historial."
        raise FiltroInvalido(mensaje, campos={"cursor": mensaje})
    return posicion


class EventoSalida(BaseModel):
    accion: str
    en: datetime
    # Quién lo hizo; nulo si la cuenta ya no existe.
    actor: str | None
    motivo: str | None
    cuota: int | None

    @classmethod
    def desde(cls, evento: Evento, nombres: dict[UUID, str]) -> "EventoSalida":
        return cls(
            accion=evento.accion,
            en=evento.en,
            actor=nombres.get(evento.actor_id) if evento.actor_id else None,
            motivo=evento.motivo,
            cuota=evento.cuota,
        )


class PagoHistorialSalida(BaseModel):
    id: UUID
    cuota: int
    importe: str
    comision: str
    mora: str
    lugar_pago: LugarPago | None
    pagado_el: date
    estado: EstadoPago
    # Solo para el gerente.
    confianza: int | None
    registrado_por: str
    registrado_en: datetime
    decidido_en: datetime | None
    motivo_decision: str | None

    @classmethod
    def desde(
        cls, pago: PagoHistorial, nombres: dict[UUID, str], *, gerente: bool
    ) -> "PagoHistorialSalida":
        return cls(
            id=pago.id,
            cuota=pago.cuota,
            importe=str(pago.importe),
            comision=str(pago.comision),
            mora=str(pago.mora),
            lugar_pago=pago.lugar_pago,
            pagado_el=pago.pagado_el,
            estado=pago.estado,
            confianza=pago.confianza if gerente else None,
            registrado_por=nombres.get(pago.registrado_por, ""),
            registrado_en=pago.registrado_en,
            decidido_en=pago.decidido_en,
            motivo_decision=pago.motivo_decision,
        )


class MoraHistorialSalida(BaseModel):
    id: UUID
    cuota: int
    importe: str
    estado: EstadoMora
    declarada_por: str
    declarada_en: datetime
    decidida_en: datetime | None
    motivo_decision: str | None

    @classmethod
    def desde(cls, mora: MoraHistorial, nombres: dict[UUID, str]) -> "MoraHistorialSalida":
        return cls(
            id=mora.id,
            cuota=mora.cuota,
            importe=str(mora.importe),
            estado=mora.estado,
            declarada_por=nombres.get(mora.declarada_por, ""),
            declarada_en=mora.declarada_en,
            decidida_en=mora.decidida_en,
            motivo_decision=mora.motivo_decision,
        )


class CuotaHistorialSalida(BaseModel):
    numero: int
    vence_el: date
    importe: str
    # El pago vigente (por verificar o confirmado); nulo si falta pagarla.
    pago: EstadoPago | None
    # La mora de la cuota que no fue rechazada.
    mora: EstadoMora | None

    @classmethod
    def desde(cls, cuota: CuotaHistorial, deuda: DeudaHistorial) -> "CuotaHistorialSalida":
        pago = deuda.pago_vigente(cuota.numero)
        mora = next(
            (
                m
                for m in reversed(deuda.moras)
                if m.cuota == cuota.numero and m.estado is not EstadoMora.RECHAZADA
            ),
            None,
        )
        return cls(
            numero=cuota.numero,
            vence_el=cuota.vence_el,
            importe=str(cuota.importe),
            pago=pago.estado if pago else None,
            mora=mora.estado if mora else None,
        )


class DeudaHistorialSalida(BaseModel):
    id: UUID
    concepto: str
    categoria_id: UUID | None
    tipo_documento: TipoDocumento
    lugares_pago: list[LugarPago]
    importe: str
    estado: EstadoDeuda
    revision_pendiente: bool
    motivos: list[str]
    registrada_por: str
    registrada_por_id: UUID
    creado_en: datetime
    motivo_decision: str | None
    cuotas: list[CuotaHistorialSalida]
    pagos: list[PagoHistorialSalida]
    moras: list[MoraHistorialSalida]
    eventos: list[EventoSalida]

    @classmethod
    def desde(
        cls, deuda: DeudaHistorial, nombres: dict[UUID, str], *, gerente: bool
    ) -> "DeudaHistorialSalida":
        return cls(
            id=deuda.id,
            concepto=deuda.concepto,
            categoria_id=deuda.categoria_id,
            tipo_documento=deuda.tipo_documento,
            lugares_pago=list(deuda.lugares_pago),
            importe=str(deuda.importe),
            estado=deuda.estado,
            revision_pendiente=deuda.revision_pendiente,
            motivos=list(deuda.motivos),
            registrada_por=nombres.get(deuda.registrada_por, ""),
            registrada_por_id=deuda.registrada_por,
            creado_en=deuda.creado_en,
            motivo_decision=deuda.motivo_decision,
            cuotas=[CuotaHistorialSalida.desde(c, deuda) for c in deuda.cuotas],
            pagos=[PagoHistorialSalida.desde(p, nombres, gerente=gerente) for p in deuda.pagos],
            moras=[MoraHistorialSalida.desde(m, nombres) for m in deuda.moras],
            eventos=[EventoSalida.desde(e, nombres) for e in deuda.eventos],
        )


class HistorialSalida(BaseModel):
    hoy: date
    # El rango aplicado: sin fechas en la consulta, los últimos 90 días.
    desde: date
    hasta: date
    deudas: list[DeudaHistorialSalida]
    # Para pedir la página siguiente; nulo si no hay más.
    siguiente: str | None

    @classmethod
    def desde_pagina(cls, pagina: PaginaHistorial) -> "HistorialSalida":
        return cls(
            hoy=pagina.hoy,
            desde=pagina.filtros.desde,
            hasta=pagina.filtros.hasta,
            deudas=[
                DeudaHistorialSalida.desde(d, pagina.nombres, gerente=pagina.gerente)
                for d in pagina.deudas
            ],
            siguiente=cifrar_cursor(pagina.siguiente) if pagina.siguiente else None,
        )
