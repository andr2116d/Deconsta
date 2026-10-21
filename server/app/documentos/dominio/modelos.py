"""Documentos que respaldan las deudas y lo que se lee de ellos.

Un documento se sube, se analiza en tres capas (lectura del texto, revisión con IA y metadatos del
archivo) y, si queda listo, respalda una sola deuda. Lo leído es una propuesta: quien registra la
revisa y la corrige, pero las reglas del espacio se aplican sobre lo que dice el documento.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

TAMANO_MAXIMO = 10 * 1024 * 1024
MAXIMO_PAGINAS = 10


class TipoArchivo(StrEnum):
    PDF = "application/pdf"
    JPEG = "image/jpeg"
    PNG = "image/png"
    WEBP = "image/webp"

    @property
    def extension(self) -> str:
        return {"application/pdf": "pdf", "image/jpeg": "jpg"}.get(self.value, self.value[6:])


class EstadoDocumento(StrEnum):
    ANALIZANDO = "analizando"
    LISTO = "listo"
    # No se pudo leer: no hay forma de comprobar a qué gasto corresponde.
    ILEGIBLE = "ilegible"
    # Ya respalda otra deuda del espacio.
    REPETIDO = "repetido"
    # Muestra señales claras de alteración y lo subió una asistente.
    RECHAZADO = "rechazado"
    # No es una deuda por pagar (un comprobante de un pago ya hecho, una cotización) y lo subió una
    # asistente.
    NO_ES_DEUDA = "no_es_deuda"
    # El análisis no pudo completarse por un problema técnico.
    FALLIDO = "fallido"


class TipoDocumento(StrEnum):
    RECIBO_SERVICIO = "recibo_servicio"
    BOLETA = "boleta"
    FACTURA = "factura"
    CRONOGRAMA = "cronograma"
    # De una tarjeta de crédito: el pago del mes es la deuda.
    ESTADO_CUENTA = "estado_cuenta"
    PAPELETA = "papeleta"
    TRIBUTO = "tributo"
    # Constancia de un pago ya hecho (Yape, Plin, transferencia, depósito, voucher de POS).
    COMPROBANTE_PAGO = "comprobante_pago"
    OTRO = "otro"


class Naturaleza(StrEnum):
    """Qué es el documento respecto de una deuda."""

    POR_PAGAR = "por_pagar"
    # Cobra algo que ya figura pagado: sello CANCELADO, nada por pagar, boleta al contado.
    YA_PAGADA = "ya_pagada"
    # Prueba un pago hecho: no cobra nada.
    PAGO_REALIZADO = "pago_realizado"
    # No es un documento de cobro: cotización, proforma, guía, nota de crédito, identidad, chat.
    NO_ES_DEUDA = "no_es_deuda"


class Riesgo(StrEnum):
    BAJO = "bajo"
    MEDIO = "medio"
    ALTO = "alto"

    @property
    def nivel(self) -> int:
        return list(Riesgo).index(self)


class Capa(StrEnum):
    LECTURA = "lectura"
    IA = "ia"
    METADATOS = "metadatos"


@dataclass(frozen=True)
class Senal:
    """Algo que se encontró al analizar el documento. `detalle` se le muestra a quien registra y,
    si hace falta, al gerente: dice qué se vio, sin datos personales."""

    capa: Capa
    codigo: str
    detalle: str
    riesgo: Riesgo


@dataclass(frozen=True)
class CuotaLeida:
    numero: int
    vence_el: date
    importe: Decimal


@dataclass(frozen=True)
class DatosLeidos:
    """Lo que la revisión con IA leyó del documento. Cualquier campo puede faltar."""

    tipo: TipoDocumento = TipoDocumento.OTRO
    naturaleza: Naturaleza = Naturaleza.POR_PAGAR
    emisor: str | None = None
    emisor_ruc: str | None = None
    concepto: str | None = None
    titular_nombre: str | None = None
    titular_tipo_documento: str | None = None
    titular_numero_documento: str | None = None
    # Suministro, código de cliente o número de crédito: lo que se da al pagar.
    codigo_pago: str | None = None
    # Serie y número del comprobante, número del recibo o de la papeleta.
    numero_documento: str | None = None
    # Mes facturado, «2026-09».
    periodo: str | None = None
    importe: Decimal | None = None
    vence_el: date | None = None
    cuotas: tuple[CuotaLeida, ...] = ()
    # Nombre de una categoría del espacio, o el de una nueva que convendría crear.
    categoria: str | None = None
    categoria_nueva: str | None = None
    lugar_pago: str | None = None


@dataclass(frozen=True)
class Lectura:
    """Texto leído por la capa de lectura (OCR), con la confianza media de sus líneas."""

    texto: str
    confianza: float
    paginas: int


@dataclass(frozen=True)
class Analisis:
    datos: DatosLeidos | None
    senales: tuple[Senal, ...] = ()

    @property
    def riesgo(self) -> Riesgo:
        return max((s.riesgo for s in self.senales), key=lambda r: r.nivel, default=Riesgo.BAJO)


@dataclass
class Documento:
    id: UUID
    gerente_id: UUID
    subido_por: UUID
    tipo_archivo: TipoArchivo
    tamano: int
    paginas: int
    nombre_archivo: str
    clave_objeto: str
    huella_archivo: bytes
    estado: EstadoDocumento
    subido_en: datetime
    clave_negocio_huella: bytes | None = None
    huellas_texto: tuple[bytes, ...] = ()
    analisis: Analisis | None = None
    analizado_en: datetime | None = None
    repetido_de: UUID | None = None
    deuda_id: UUID | None = None
    tipo_documento: TipoDocumento | None = None

    @property
    def registrable(self) -> bool:
        return self.estado is EstadoDocumento.LISTO and self.deuda_id is None


@dataclass(frozen=True)
class DeudaDelDocumento:
    """Deuda que ya usa un documento: se le dice a quien lo vuelve a subir dónde lo usó."""

    id: UUID
    concepto: str
    registrada_en: datetime
