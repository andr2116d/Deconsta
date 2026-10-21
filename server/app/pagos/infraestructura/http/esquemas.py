from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.esquemas import Entrada
from app.deudas.dominio.modelos import EstadoPago, LugarPago
from app.documentos.dominio.bloqueos import Bloqueo
from app.documentos.dominio.modelos import Riesgo, TipoDocumento
from app.documentos.infraestructura.http.esquemas import SenalSalida
from app.pagos.aplicacion.pagos import (
    ComprobanteConsultado,
    CuotaPorPagar,
    MoraConDetalle,
    MoraConPrueba,
    PagoConComprobantes,
    PagoConDetalle,
    PorPagar,
)
from app.pagos.dominio.modelos import (
    Comprobacion,
    DatosComprobante,
    EstadoComprobante,
    EstadoMora,
    Mora,
    Proposito,
    ResultadoComprobacion,
)


class LecturaSalida(BaseModel):
    """Lo que se leyó del comprobante, para que quien lo subió lo reconozca. Sin el titular ni el
    código de pago: ya figuran en la deuda."""

    lugar: LugarPago | None
    medio: str | None
    empresa: str | None
    numero_operacion: str | None
    pagado_el: date | None
    # En soles, como texto: lo pagado por el servicio y la comisión aparte.
    importe: str | None
    comision: str | None
    # En la prueba de una mora: la mora, si figura aparte.
    mora: str | None

    @classmethod
    def desde(cls, datos: DatosComprobante) -> "LecturaSalida":
        return cls(
            lugar=datos.lugar,
            medio=datos.medio,
            empresa=datos.empresa,
            numero_operacion=datos.numero_operacion,
            pagado_el=datos.pagado_el,
            importe=str(datos.importe) if datos.importe is not None else None,
            comision=str(datos.comision) if datos.comision is not None else None,
            mora=str(datos.mora) if datos.mora is not None else None,
        )


class ComprobanteSalida(BaseModel):
    id: UUID
    deuda_id: UUID
    cuota: int
    estado: EstadoComprobante
    tipo_archivo: str
    nombre_archivo: str
    tamano: int
    subido_en: datetime
    analizado_en: datetime | None
    riesgo: Riesgo | None
    senales: list[SenalSalida]
    lectura: LecturaSalida | None
    pago_id: UUID | None
    # El voucher de un pago o la prueba de una mora.
    proposito: Proposito
    # Si quien lo subió tiene el registro de pagos en pausa.
    registro_bloqueado: bool

    @classmethod
    def desde(cls, consulta: ComprobanteConsultado) -> "ComprobanteSalida":
        comprobante = consulta.comprobante
        analisis = comprobante.analisis
        return cls(
            id=comprobante.id,
            deuda_id=comprobante.deuda_id,
            cuota=comprobante.cuota,
            estado=comprobante.estado,
            tipo_archivo=comprobante.tipo_archivo.value,
            nombre_archivo=comprobante.nombre_archivo,
            tamano=comprobante.tamano,
            subido_en=comprobante.subido_en,
            analizado_en=comprobante.analizado_en,
            riesgo=analisis.riesgo if analisis else None,
            senales=[SenalSalida.desde(s) for s in analisis.senales] if analisis else [],
            lectura=LecturaSalida.desde(analisis.datos) if analisis and analisis.datos else None,
            pago_id=comprobante.pago_id,
            proposito=comprobante.proposito,
            registro_bloqueado=consulta.registro_bloqueado,
        )


class MoraResumen(BaseModel):
    id: UUID
    estado: EstadoMora
    importe: str
    motivo_decision: str | None

    @classmethod
    def desde(cls, mora: Mora) -> "MoraResumen":
        return cls(
            id=mora.id,
            estado=mora.estado,
            importe=str(mora.importe),
            motivo_decision=mora.motivo_decision,
        )


class CuotaPorPagarSalida(BaseModel):
    deuda_id: UUID
    concepto: str
    categoria_id: UUID | None
    tipo_documento: TipoDocumento
    lugares_pago: list[LugarPago]
    codigo_pago: str | None
    cuota: int
    cuotas: int
    vence_el: date
    # En soles: el importe de esta cuota.
    importe: str
    vencida_hace: int | None
    registrada_por: str
    # Por qué el gerente devolvió el último pago de esta cuota, si lo devolvió.
    devuelto_por: str | None
    # La mora vigente de la cuota o, si no hay, la última rechazada.
    mora: MoraResumen | None

    @classmethod
    def desde(cls, item: CuotaPorPagar) -> "CuotaPorPagarSalida":
        deuda, cuota = item.deuda, item.cuota
        return cls(
            deuda_id=deuda.id,
            concepto=deuda.concepto,
            categoria_id=deuda.categoria_id,
            tipo_documento=deuda.tipo_documento,
            lugares_pago=list(deuda.lugares_pago),
            codigo_pago=deuda.codigo_pago,
            cuota=cuota.numero,
            cuotas=len(deuda.cuotas),
            vence_el=cuota.vence_el,
            importe=str(cuota.importe),
            vencida_hace=item.vencida_hace,
            registrada_por=item.registrada_por,
            devuelto_por=item.devuelto_por,
            mora=MoraResumen.desde(item.mora) if item.mora else None,
        )


class PorPagarSalida(BaseModel):
    hoy: date
    cuotas: list[CuotaPorPagarSalida]
    registro_bloqueado: bool

    @classmethod
    def desde(cls, por_pagar: PorPagar) -> "PorPagarSalida":
        return cls(
            hoy=por_pagar.hoy,
            cuotas=[CuotaPorPagarSalida.desde(c) for c in por_pagar.cuotas],
            registro_bloqueado=por_pagar.registro_bloqueado,
        )


class PagoEntrada(Entrada):
    deuda_id: UUID
    cuota: int = Field(ge=1, le=360)
    comprobantes: list[UUID] = Field(default_factory=list, max_length=10)


class ComprobacionSalida(BaseModel):
    codigo: str
    titulo: str
    resultado: ResultadoComprobacion
    detalle: str

    @classmethod
    def desde(cls, comprobacion: Comprobacion) -> "ComprobacionSalida":
        return cls(
            codigo=comprobacion.codigo,
            titulo=comprobacion.titulo,
            resultado=comprobacion.resultado,
            detalle=comprobacion.detalle,
        )


class PagoSalida(BaseModel):
    id: UUID
    deuda_id: UUID
    concepto: str
    cuota: int
    importe: str
    comision: str
    # Lo pagado por una mora aprobada, dentro del importe.
    mora: str
    lugar_pago: LugarPago | None
    pagado_el: date
    estado: EstadoPago
    # Solo para el gerente: cuánto respaldan los comprobantes el pago y por qué. A una asistente
    # no se le dice qué comprobaciones pasó un voucher.
    confianza: int | None
    comprobaciones: list[ComprobacionSalida] | None
    comprobantes: list[UUID]
    registrado_por: str
    registrado_en: datetime
    decidido_en: datetime | None
    motivo_decision: str | None

    @classmethod
    def desde(cls, detalle: PagoConDetalle, *, gerente: bool) -> "PagoSalida":
        pago = detalle.pago
        return cls(
            id=pago.id,
            deuda_id=pago.deuda_id,
            concepto=detalle.concepto,
            cuota=pago.cuota,
            importe=str(pago.importe),
            comision=str(pago.comision),
            mora=str(pago.mora),
            lugar_pago=pago.lugar,
            pagado_el=pago.pagado_el,
            estado=pago.estado,
            confianza=pago.confianza if gerente else None,
            comprobaciones=[ComprobacionSalida.desde(c) for c in pago.comprobaciones]
            if gerente
            else None,
            comprobantes=list(pago.comprobantes),
            registrado_por=detalle.registrado_por,
            registrado_en=pago.registrado_en,
            decidido_en=pago.decidido_en,
            motivo_decision=pago.motivo_decision,
        )


class PagoDetalleSalida(PagoSalida):
    cuotas: int
    detalle_comprobantes: list[ComprobanteSalida]

    @classmethod
    def detalle(cls, consulta: PagoConComprobantes, *, gerente: bool) -> "PagoDetalleSalida":
        base = PagoSalida.desde(consulta.detalle, gerente=gerente)
        return cls(
            **base.model_dump(),
            cuotas=consulta.cuotas,
            detalle_comprobantes=[
                ComprobanteSalida.desde(ComprobanteConsultado(c, registro_bloqueado=False))
                for c in consulta.comprobantes
            ],
        )


class MotivoEntrada(Entrada):
    motivo: str | None = Field(None, max_length=1000)


class BloqueoPagosSalida(BaseModel):
    asistente_id: UUID
    bloqueado_en: datetime

    @classmethod
    def desde(cls, bloqueo: Bloqueo) -> "BloqueoPagosSalida":
        return cls(asistente_id=bloqueo.asistente_id, bloqueado_en=bloqueo.bloqueado_en)


class MoraEntrada(Entrada):
    deuda_id: UUID
    cuota: int = Field(ge=1, le=360)
    # En soles, como texto («14.40»): nunca como número de coma flotante.
    importe: str = Field("", max_length=20)
    prueba_id: UUID
    nota: str | None = Field(None, max_length=1000)


class MoraSalida(BaseModel):
    id: UUID
    deuda_id: UUID
    concepto: str
    cuota: int
    # En soles: la mora y el importe de la cuota sin ella.
    importe: str
    importe_cuota: str
    nota: str | None
    estado: EstadoMora
    # Solo para el gerente, como en los pagos.
    confianza: int | None
    comprobaciones: list[ComprobacionSalida] | None
    prueba_id: UUID
    declarada_por: str
    declarada_en: datetime
    decidida_en: datetime | None
    motivo_decision: str | None

    @classmethod
    def desde(cls, detalle: MoraConDetalle, *, gerente: bool) -> "MoraSalida":
        mora = detalle.mora
        return cls(
            id=mora.id,
            deuda_id=mora.deuda_id,
            concepto=detalle.concepto,
            cuota=mora.cuota,
            importe=str(mora.importe),
            importe_cuota=str(detalle.cuota),
            nota=mora.nota,
            estado=mora.estado,
            confianza=mora.confianza if gerente else None,
            comprobaciones=[ComprobacionSalida.desde(c) for c in mora.comprobaciones]
            if gerente
            else None,
            prueba_id=mora.prueba_id,
            declarada_por=detalle.declarada_por,
            declarada_en=mora.declarada_en,
            decidida_en=mora.decidida_en,
            motivo_decision=mora.motivo_decision,
        )


class MoraDetalleSalida(MoraSalida):
    prueba: ComprobanteSalida | None

    @classmethod
    def detalle(cls, consulta: MoraConPrueba, *, gerente: bool) -> "MoraDetalleSalida":
        base = MoraSalida.desde(consulta.detalle, gerente=gerente)
        prueba = consulta.prueba
        return cls(
            **base.model_dump(),
            prueba=ComprobanteSalida.desde(ComprobanteConsultado(prueba, registro_bloqueado=False))
            if prueba
            else None,
        )
