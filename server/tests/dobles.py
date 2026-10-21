"""Adaptadores en memoria para probar los documentos sin bucket, sin PaddleOCR y sin la API de
Claude. La base, Redis y el cifrado son los reales."""

import io
from dataclasses import dataclass, field
from uuid import UUID

from PIL import Image, ImageDraw
from pypdf import PdfWriter

from app.documentos.aplicacion.documentos import AnalizarDocumento
from app.documentos.dominio.modelos import DatosLeidos, Lectura, TipoArchivo
from app.documentos.dominio.puertos import (
    CategoriaConocida,
    ErrorAlmacen,
    ErrorRevision,
    RevisionIa,
)
from app.documentos.infraestructura.almacen_s3 import CifradorArchivos
from app.notificaciones.dominio.modelos import Notificacion

TEXTO_RECIBO = """HIDRANDINA S.A. RUC 20132023540
RECIBO N. S001-00451236
Suministro: 54871236
Titular: VALENTINA RAMOS DIAZ
Periodo: SETIEMBRE 2026
Fecha de vencimiento: 28/10/2026
TOTAL A PAGAR S/ 182.40"""


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


class ColaInmediata:
    """Analiza en el acto, como lo haría el worker. Pausada, deja los documentos «analizando»."""

    def __init__(self) -> None:
        self.analizar: AnalizarDocumento | None = None
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
