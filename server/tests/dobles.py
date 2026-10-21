"""Adaptadores en memoria para probar los documentos sin bucket, sin PaddleOCR y sin la API de
Claude. La base, Redis y el cifrado son los reales."""

import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfWriter

from app.deudas.dominio.modelos import LugarPago
from app.documentos.dominio.modelos import DatosLeidos, Lectura, TipoArchivo
from app.documentos.dominio.puertos import (
    CategoriaConocida,
    ErrorAlmacen,
    ErrorRevision,
    RevisionIa,
)
from app.documentos.infraestructura.almacen_s3 import CifradorArchivos
from app.notificaciones.dominio.modelos import Notificacion
from app.pagos.dominio.modelos import DatosComprobante, Moneda
from app.pagos.dominio.puertos import RevisionComprobante

TEXTO_RECIBO = """HIDRANDINA S.A. RUC 20132023540
RECIBO N. S001-00451236
Suministro: 54871236
Titular: VALENTINA RAMOS DIAZ
Periodo: SETIEMBRE 2026
Fecha de vencimiento: 28/10/2026
TOTAL A PAGAR S/ 182.40"""

TEXTO_VOUCHER = """AGENTE BCP - PAGO DE SERVICIOS
HIDRANDINA S.A.
Suministro: 54871236
Nro. Operacion: 0458213
Fecha: 21/10/2026 10:42
Importe: S/ 182.40"""

VOUCHER = DatosComprobante(
    lugar=LugarPago.AGENTE,
    medio="Agente BCP",
    empresa="HIDRANDINA",
    codigo_pago="54871236",
    numero_operacion="0458213",
    pagado_el=date(2026, 10, 21),
    moneda=Moneda.SOLES,
    importe=Decimal("182.40"),
    total=Decimal("182.40"),
)


class AlmacenEnMemoria:
    """Cifra como el adaptador real: lo guardado nunca es el archivo original."""

    def __init__(self, clave: bytes) -> None:
        self._cifrador = CifradorArchivos(clave)
        self.objetos: dict[str, bytes] = {}

    def guardar(self, clave: str, contenido: bytes, tipo: TipoArchivo) -> None:
        self.objetos[clave] = self._cifrador.cifrar(contenido, clave)

    def leer(self, clave: str) -> bytes:
        if clave not in self.objetos:
            raise ErrorAlmacen("No existe")
        return self._cifrador.descifrar(self.objetos[clave], clave)


@dataclass
class LectorDePrueba:
    texto: str = TEXTO_RECIBO
    confianza: float = 0.97
    lecturas: int = 0

    def leer(self, contenido: bytes, tipo: TipoArchivo) -> Lectura:
        self.lecturas += 1
        return Lectura(self.texto, self.confianza, 1)


@dataclass
class RevisorDePrueba:
    datos: DatosLeidos = field(default_factory=DatosLeidos)
    veredicto: str = "autentico"
    motivos: tuple[str, ...] = ()
    legible: bool = True
    falla: bool = False
    revisiones: int = 0
    categorias: list[CategoriaConocida] = field(default_factory=list)
    # Lo que lee de un comprobante de pago.
    comprobante: DatosComprobante = VOUCHER
    veredicto_comprobante: str = "autentico"
    comprobantes_revisados: int = 0

    def revisar_comprobante(
        self, contenido: bytes, tipo: TipoArchivo, lectura: Lectura
    ) -> RevisionComprobante:
        self.comprobantes_revisados += 1
        if self.falla:
            raise ErrorRevision("Sin conexión")
        return RevisionComprobante(
            self.legible, self.comprobante, self.veredicto_comprobante, self.motivos
        )

    def revisar(
        self,
        contenido: bytes,
        tipo: TipoArchivo,
        lectura: Lectura,
        categorias: list[CategoriaConocida],
    ) -> RevisionIa:
        self.revisiones += 1
        self.categorias = categorias
        if self.falla:
            raise ErrorRevision("Sin conexión")
        return RevisionIa(self.legible, self.datos, self.veredicto, self.motivos)


@dataclass
class PublicadorEnMemoria:
    avisos: list[Notificacion] = field(default_factory=list)

    def avisar(self, notificacion: Notificacion) -> None:
        self.avisos.append(notificacion)


class Analizador(Protocol):
    def ejecutar(self, identificador: UUID, /) -> object: ...


class ColaInmediata:
    """Analiza en el acto, como lo haría el worker. Pausada, deja los archivos «analizando»."""

    def __init__(self) -> None:
        self.analizar: Analizador | None = None
        self.pausada = False
        self.pendientes: list[UUID] = []

    def encolar(self, documento_id: UUID) -> None:
        if self.pausada:
            self.pendientes.append(documento_id)
            return
        assert self.analizar is not None
        self.analizar.ejecutar(documento_id)


@dataclass
class Dobles:
    almacen: AlmacenEnMemoria
    lector: LectorDePrueba
    revisor: RevisorDePrueba
    publicador: PublicadorEnMemoria
    cola: ColaInmediata
    cola_comprobantes: ColaInmediata = field(default_factory=ColaInmediata)


def imagen(semilla: int = 0, formato: str = "PNG") -> bytes:
    """Una imagen válida y distinta por semilla: cambia su huella de archivo."""
    lienzo = Image.new("RGB", (800, 600), "white")
    dibujo = ImageDraw.Draw(lienzo)
    dibujo.rectangle((10, 10, 20 + semilla % 700, 30), fill="black")
    dibujo.text((40, 100), f"Recibo {semilla}", fill="black")
    salida = io.BytesIO()
    lienzo.save(salida, format=formato)
    return salida.getvalue()


def pdf(productor: str | None = None, *, paginas: int = 1) -> bytes:
    escritor = PdfWriter()
    for _ in range(paginas):
        escritor.add_blank_page(width=595, height=842)
    if productor:
        escritor.add_metadata({"/Producer": productor})
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


TEXTO_YAPE = """Yapeaste!
S/182.40
Pago de servicio
HIDRANDINA - LUZ
Código de suministro
54871236
Fecha
21 oct. 2026 - 10:42 a. m.
Nro. de operación
03458821"""


def captura_yape() -> bytes:
    """Una captura tipo Yape del pago de la luz, con datos inventados, para la IA real."""
    lienzo = Image.new("RGB", (720, 1400), "#742284")
    dibujo = ImageDraw.Draw(lienzo)
    dibujo.rounded_rectangle((40, 160, 680, 1250), 30, fill="white")
    fuente = ImageFont.load_default(size=40)
    y = 220
    for linea in TEXTO_YAPE.splitlines():
        dibujo.text((90, y), linea, font=fuente, fill="#222222")
        y += 70
    salida = io.BytesIO()
    lienzo.save(salida, format="PNG")
    return salida.getvalue()
