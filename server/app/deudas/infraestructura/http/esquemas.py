from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.acceso.infraestructura.http.esquemas import enmascarar, exigir
from app.core.esquemas import Entrada
from app.deudas.aplicacion.deudas import Calendario, DeudaConDetalle, NuevaDeuda, Vencimiento
from app.deudas.dominio.modelos import Deuda, EstadoDeuda, LugarPago, MotivoEspera
from app.deudas.dominio.registro import CuotaEnviada
from app.documentos.dominio.modelos import TipoDocumento
from app.documentos.infraestructura.http.esquemas import DocumentoSalida


class CuotaEntrada(Entrada):
    vence_el: date | None = None
    # En soles, como texto («182.40»): nunca como número de coma flotante.
    importe: str = Field("", max_length=20)


class DeudaEntrada(Entrada):
    documento_id: UUID
    # Los topes son holgados: el dominio da el mensaje preciso de cada regla.
    concepto: str = Field("", max_length=200, validate_default=True)
    categoria_id: UUID | None = None
    # Uno o varios: la luz, por ejemplo, se paga en un agente, por Yape o por banca por internet.
    lugares_pago: list[Annotated[str, Field(max_length=30)]] = Field(
        default_factory=list, max_length=10
    )
    cuotas: list[CuotaEntrada] = Field(default_factory=list, max_length=400)
    titular_nombre: str | None = Field(None, max_length=200)
    titular_tipo_documento: str | None = Field(None, max_length=10)
    titular_numero_documento: str | None = Field(None, max_length=30)
    codigo_pago: str | None = Field(None, max_length=80)

    @field_validator("concepto")
    @classmethod
    def validar_concepto(cls, valor: str) -> str:
        return exigir(valor, "Escribe un nombre para la deuda, por ejemplo «Luz de la casa».")

    def nueva(self) -> NuevaDeuda:
        return NuevaDeuda(
            documento_id=self.documento_id,
            concepto=self.concepto,
            lugares_pago=self.lugares_pago,
            cuotas=[CuotaEnviada(c.vence_el, c.importe) for c in self.cuotas],
            categoria_id=self.categoria_id,
            titular_nombre=self.titular_nombre,
            titular_tipo_documento=self.titular_tipo_documento,
            titular_numero_documento=self.titular_numero_documento,
            codigo_pago=self.codigo_pago,
        )


class MotivoObligatorioEntrada(Entrada):
    motivo: str | None = Field(None, max_length=1000)


class CuotaSalida(BaseModel):
    numero: int
    vence_el: date
    importe: str


class RegistradaPor(BaseModel):
    id: UUID
    nombre: str


class DeudaSalida(BaseModel):
    id: UUID
    documento_id: UUID
    concepto: str
    categoria_id: UUID | None
    tipo_documento: TipoDocumento
    importe: str
    vence_el: date
    cuotas: list[CuotaSalida]
    lugares_pago: list[LugarPago]
    titular_nombre: str | None
    titular_tipo_documento: str | None
    # Enmascarado: el gerente lo reconoce por sus últimos dígitos.
    titular_documento: str | None
    codigo_pago: str | None
    estado: EstadoDeuda
    motivos: list[MotivoEspera]
    revision_pendiente: bool
    campos_corregidos: list[str]
    registrada_por: RegistradaPor
    creado_en: datetime
    decidida_en: datetime | None
    motivo_decision: str | None

    @classmethod
    def desde(cls, deuda: Deuda, registrada_por: str) -> "DeudaSalida":
        documento = deuda.titular_documento
        return cls(
            id=deuda.id,
            documento_id=deuda.documento_id,
            concepto=deuda.concepto,
            categoria_id=deuda.categoria_id,
            tipo_documento=deuda.tipo_documento,
            importe=str(deuda.importe),
            vence_el=deuda.vence_el,
            cuotas=[
                CuotaSalida(numero=c.numero, vence_el=c.vence_el, importe=str(c.importe))
                for c in deuda.cuotas
            ],
            lugares_pago=list(deuda.lugares_pago),
            titular_nombre=deuda.titular_nombre,
            titular_tipo_documento=documento.tipo.value if documento else None,
            titular_documento=enmascarar(documento.numero) if documento else None,
            codigo_pago=deuda.codigo_pago,
            estado=deuda.estado,
            motivos=list(deuda.motivos),
            revision_pendiente=deuda.revision_pendiente,
            campos_corregidos=list(deuda.campos_corregidos),
            registrada_por=RegistradaPor(id=deuda.registrada_por, nombre=registrada_por),
            creado_en=deuda.creado_en,
            decidida_en=deuda.decidida_en,
            motivo_decision=deuda.motivo_decision,
        )

    @classmethod
    def con_detalle(cls, detalle: DeudaConDetalle) -> "DeudaSalida":
        return cls.desde(detalle.deuda, detalle.registrada_por)


class RegistroSalida(BaseModel):
    deuda: DeudaSalida
    # Lo que se le advierte al gerente cuando la registra él mismo.
    avisos: list[str]


class VencimientoSalida(BaseModel):
    deuda_id: UUID
    concepto: str
    categoria_id: UUID | None
    tipo_documento: TipoDocumento
    lugares_pago: list[LugarPago]
    estado: EstadoDeuda
    revision_pendiente: bool
    vence_el: date
    # En soles: el importe de esta cuota, no el de toda la deuda.
    importe: str
    cuota: int
    # Cuántas cuotas tiene la deuda: 1 en un recibo.
    cuotas: int
    registrada_por: str

    @classmethod
    def desde(cls, vencimiento: Vencimiento) -> "VencimientoSalida":
        deuda, cuota = vencimiento.deuda, vencimiento.cuota
        return cls(
            deuda_id=deuda.id,
            concepto=deuda.concepto,
            categoria_id=deuda.categoria_id,
            tipo_documento=deuda.tipo_documento,
            lugares_pago=list(deuda.lugares_pago),
            estado=deuda.estado,
            revision_pendiente=deuda.revision_pendiente,
            vence_el=cuota.vence_el,
            importe=str(cuota.importe),
            cuota=cuota.numero,
            cuotas=len(deuda.cuotas),
            registrada_por=vencimiento.registrada_por,
        )


class CalendarioSalida(BaseModel):
    hoy: date
    desde: date
    hasta: date
    vencimientos: list[VencimientoSalida]

    @classmethod
    def desde_calendario(cls, calendario: Calendario) -> "CalendarioSalida":
        return cls(
            hoy=calendario.hoy,
            desde=calendario.desde,
            hasta=calendario.hasta,
            vencimientos=[VencimientoSalida.desde(v) for v in calendario.vencimientos],
        )


class DeudaDetalleSalida(DeudaSalida):
    documento: DocumentoSalida | None

    @classmethod
    def detalle(cls, detalle: DeudaConDetalle) -> "DeudaDetalleSalida":
        base = DeudaSalida.con_detalle(detalle)
        documento = DocumentoSalida.desde(detalle.documento) if detalle.documento else None
        return cls(**base.model_dump(), documento=documento)
