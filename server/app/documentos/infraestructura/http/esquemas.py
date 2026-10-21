from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.documentos.aplicacion.documentos import DocumentoConsultado
from app.documentos.dominio.bloqueos import Bloqueo
from app.documentos.dominio.modelos import (
    DatosLeidos,
    DeudaDelDocumento,
    Documento,
    EstadoDocumento,
    Riesgo,
    Senal,
    TipoDocumento,
)


class SenalSalida(BaseModel):
    capa: str
    codigo: str
    detalle: str
    riesgo: Riesgo

    @classmethod
    def desde(cls, senal: Senal) -> "SenalSalida":
        return cls(capa=senal.capa, codigo=senal.codigo, detalle=senal.detalle, riesgo=senal.riesgo)


class CuotaPropuesta(BaseModel):
    numero: int
    vence_el: date
    # En soles, como texto: «182.40».
    importe: str


class PropuestaSalida(BaseModel):
    """Lo que se leyó del documento para llenar el formulario. Es una propuesta: se revisa."""

    tipo: TipoDocumento
    concepto: str | None
    emisor: str | None
    titular_nombre: str | None
    titular_tipo_documento: str | None
    titular_numero_documento: str | None
    codigo_pago: str | None
    numero_documento: str | None
    periodo: str | None
    importe: str | None
    vence_el: date | None
    cuotas: list[CuotaPropuesta]
    # Nombre de una categoría del espacio, o el de una nueva que convendría crear.
    categoria: str | None
    categoria_nueva: str | None
    lugar_pago: str | None

    @classmethod
    def desde(cls, datos: DatosLeidos) -> "PropuestaSalida":
        return cls(
            tipo=datos.tipo,
            concepto=datos.concepto,
            emisor=datos.emisor,
            titular_nombre=datos.titular_nombre,
            titular_tipo_documento=datos.titular_tipo_documento,
            titular_numero_documento=datos.titular_numero_documento,
            codigo_pago=datos.codigo_pago,
            numero_documento=datos.numero_documento,
            periodo=datos.periodo,
            importe=str(datos.importe) if datos.importe is not None else None,
            vence_el=datos.vence_el,
            cuotas=[
                CuotaPropuesta(numero=c.numero, vence_el=c.vence_el, importe=str(c.importe))
                for c in datos.cuotas
            ],
            categoria=datos.categoria,
            categoria_nueva=datos.categoria_nueva,
            lugar_pago=datos.lugar_pago,
        )


class DeudaDelDocumentoSalida(BaseModel):
    id: UUID
    concepto: str
    registrada_en: datetime

    @classmethod
    def desde(cls, deuda: DeudaDelDocumento) -> "DeudaDelDocumentoSalida":
        return cls(id=deuda.id, concepto=deuda.concepto, registrada_en=deuda.registrada_en)


class DocumentoSalida(BaseModel):
    id: UUID
    estado: EstadoDocumento
    tipo_archivo: str
    nombre_archivo: str
    tamano: int
    paginas: int
    subido_en: datetime
    analizado_en: datetime | None
    riesgo: Riesgo | None
    senales: list[SenalSalida]
    propuesta: PropuestaSalida | None
    repetido_de: DeudaDelDocumentoSalida | None
    deuda_id: UUID | None

    @classmethod
    def desde(
        cls, documento: Documento, repetido_de: DeudaDelDocumento | None = None
    ) -> "DocumentoSalida":
        analisis = documento.analisis
        return cls(
            id=documento.id,
            estado=documento.estado,
            tipo_archivo=documento.tipo_archivo.value,
            nombre_archivo=documento.nombre_archivo,
            tamano=documento.tamano,
            paginas=documento.paginas,
            subido_en=documento.subido_en,
            analizado_en=documento.analizado_en,
            riesgo=analisis.riesgo if analisis else None,
            senales=[SenalSalida.desde(s) for s in analisis.senales] if analisis else [],
            propuesta=PropuestaSalida.desde(analisis.datos)
            if analisis and analisis.datos
            else None,
            repetido_de=DeudaDelDocumentoSalida.desde(repetido_de) if repetido_de else None,
            deuda_id=documento.deuda_id,
        )

    @classmethod
    def consultado(cls, consulta: DocumentoConsultado) -> "DocumentoSalida":
        return cls.desde(consulta.documento, consulta.repetido_de)


class BloqueoSalida(BaseModel):
    asistente_id: UUID
    bloqueado_en: datetime

    @classmethod
    def desde(cls, bloqueo: Bloqueo) -> "BloqueoSalida":
        return cls(asistente_id=bloqueo.asistente_id, bloqueado_en=bloqueo.bloqueado_en)
