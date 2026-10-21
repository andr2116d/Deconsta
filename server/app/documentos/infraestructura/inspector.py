"""Inspección de archivos: páginas, integridad y metadatos.

- PDF (pypdf): rechaza los dañados, los protegidos con contraseña y los de más de MAXIMO_PAGINAS.
  Lee Producer y Creator, las fechas, si trae JavaScript o firma digital y cuántas veces se guardó
  (cada actualización incremental agrega un marcador %%EOF).
- Imágenes (Pillow): comprueba que se puedan decodificar, que no sean diminutas ni enormes en
  píxeles (una bomba de descompresión) y lee del EXIF el programa y las fechas.
"""

import io
import logging
import re
from collections.abc import Mapping
from datetime import datetime

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.documentos.dominio.analisis import Metadatos
from app.documentos.dominio.errores import ArchivoInvalido, DemasiadasPaginas, PdfProtegido
from app.documentos.dominio.modelos import MAXIMO_PAGINAS, TipoArchivo
from app.documentos.dominio.puertos import Examen

logger = logging.getLogger(__name__)

# Una foto de un recibo tiene al menos unos cientos de píxeles por lado; 50 megapíxeles bastan
# para cualquier cámara de celular y frenan las imágenes armadas para agotar la memoria.
LADO_MINIMO = 300
PIXELES_MAXIMOS = 50_000_000
EXIF_SOFTWARE = 0x0131
EXIF_FECHA = 0x0132
EXIF_FECHA_ORIGINAL = 0x9003
SUBIFD_EXIF = 0x8769
PATRON_JAVASCRIPT = re.compile(rb"/(JavaScript|JS)(?![A-Za-z])")

DAÑADO = "No pudimos abrir el archivo: parece dañado. Vuelve a descargarlo o tomar la foto."


def _fecha_pdf(valor: object) -> datetime | None:
    """D:20261021093000-05'00' → datetime con zona."""
    if not isinstance(valor, str):
        return None
    coincidencia = re.match(r"D:(\d{14})(Z|[+-]\d{2}'?\d{2}'?)?", valor)
    if not coincidencia:
        return None
    zona = (coincidencia.group(2) or "Z").replace("'", "")
    zona = "+0000" if zona == "Z" else zona
    try:
        return datetime.strptime(coincidencia.group(1) + zona, "%Y%m%d%H%M%S%z")
    except ValueError:
        return None


def _fecha_exif(valor: object) -> datetime | None:
    try:
        return datetime.strptime(str(valor).strip(), "%Y:%m:%d %H:%M:%S") if valor else None
    except ValueError:
        return None


class InspectorArchivosLocal:
    def examinar(self, contenido: bytes, tipo: TipoArchivo) -> Examen:
        if tipo is TipoArchivo.PDF:
            return self._pdf(contenido)
        return self._imagen(contenido)

    @staticmethod
    def _pdf(contenido: bytes) -> Examen:
        try:
            lector = PdfReader(io.BytesIO(contenido))
            if lector.is_encrypted:
                raise PdfProtegido()
            paginas = len(lector.pages)
            info: Mapping[str, object] = lector.metadata or {}
        except (PdfReadError, KeyError, ValueError, TypeError) as error:
            raise ArchivoInvalido(DAÑADO) from error
        if paginas < 1:
            raise ArchivoInvalido(DAÑADO)
        if paginas > MAXIMO_PAGINAS:
            raise DemasiadasPaginas(MAXIMO_PAGINAS)
        programas = tuple(
            dict.fromkeys(
                str(info.get(campo)).strip()
                for campo in ("/Producer", "/Creator")
                if info.get(campo) and str(info.get(campo)).strip()
            )
        )
        return Examen(
            paginas,
            Metadatos(
                programas=programas,
                creado_en=_fecha_pdf(info.get("/CreationDate")),
                modificado_en=_fecha_pdf(info.get("/ModDate")),
                revisiones=max(contenido.count(b"%%EOF"), 1),
                # Una firma digital agrega su propia actualización incremental.
                firmado=b"/ByteRange" in contenido and b"/Sig" in contenido,
                con_javascript=PATRON_JAVASCRIPT.search(contenido) is not None,
            ),
        )

    @staticmethod
    def _imagen(contenido: bytes) -> Examen:
        try:
            # verify() revisa la estructura sin decodificar los píxeles; después hay que reabrir.
            with Image.open(io.BytesIO(contenido)) as imagen:
                imagen.verify()
            with Image.open(io.BytesIO(contenido)) as imagen:
                ancho, alto = imagen.size
                if ancho * alto > PIXELES_MAXIMOS:
                    raise ArchivoInvalido(
                        "La imagen es demasiado grande. Súbela con menos resolución."
                    )
                imagen.load()
                exif = imagen.getexif()
        except (
            UnidentifiedImageError,
            OSError,
            SyntaxError,
            Image.DecompressionBombError,
        ) as error:
            raise ArchivoInvalido(DAÑADO) from error
        if min(ancho, alto) < LADO_MINIMO:
            raise ArchivoInvalido(
                "La imagen es muy pequeña para leer el documento. Sube una foto más nítida."
            )
        detalle = exif.get_ifd(SUBIFD_EXIF) if exif else {}
        software = str(exif.get(EXIF_SOFTWARE) or "").strip()
        return Examen(
            1,
            Metadatos(
                programas=(software,) if software else (),
                creado_en=_fecha_exif(detalle.get(EXIF_FECHA_ORIGINAL)),
                modificado_en=_fecha_exif(exif.get(EXIF_FECHA)),
            ),
        )
