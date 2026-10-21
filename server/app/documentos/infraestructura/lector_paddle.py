"""Primera capa del análisis: lectura del texto con PaddleOCR, en CPU y sin IA generativa.

- PDF: se rasterizan con pdfium las primeras MAXIMO_PAGINAS_LECTURA páginas a 200 ppp. Un
  cronograma ocupa pocas páginas; el límite evita que un PDF largo ocupe el worker.
- Imágenes: se corrige la orientación EXIF y se reducen a LADO_MAXIMO píxeles; una foto de 4000 px
  no lee mejor y tarda varias veces más.
- El modelo se carga una vez por proceso y el worker lo precarga al iniciar. Solo lo usa el worker
  de la cola ocr: requiere el grupo de dependencias ocr (uv sync --group ocr).
"""

import io
import logging
import threading
from typing import Any

import pypdfium2 as pdfium
from PIL import Image, ImageOps

from app.documentos.dominio.modelos import Lectura, TipoArchivo
from app.documentos.dominio.puertos import ErrorLectura

logger = logging.getLogger(__name__)

MAXIMO_PAGINAS_LECTURA = 5
ESCALA_PDF = 200 / 72
LADO_MAXIMO = 2000
IDIOMA = "es"


def paginas_de(contenido: bytes, tipo: TipoArchivo) -> list[Image.Image]:
    try:
        if tipo is TipoArchivo.PDF:
            documento = pdfium.PdfDocument(contenido)
            try:
                return [
                    _reducir(documento[i].render(scale=ESCALA_PDF).to_pil())
                    for i in range(min(len(documento), MAXIMO_PAGINAS_LECTURA))
                ]
            finally:
                documento.close()
        return [_reducir(Image.open(io.BytesIO(contenido)))]
    except (pdfium.PdfiumError, OSError) as error:
        raise ErrorLectura("No se pudo convertir el documento en imágenes") from error


def _reducir(imagen: Image.Image) -> Image.Image:
    imagen = ImageOps.exif_transpose(imagen) or imagen
    imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    return imagen.convert("RGB")


class LectorPaddle:
    """PaddleOCR 3 con el modelo de español. Sin clasificador de orientación ni corrección de
    deformación: los documentos son fotos o capturas planas y esos modelos duplican el tiempo."""

    def __init__(self) -> None:
        self._ocr: Any = None
        # Una instancia de Paddle no admite lecturas simultáneas desde varios hilos.
        self._bloqueo = threading.Lock()

    def precargar(self) -> None:
        with self._bloqueo:
            self._motor()

    def _motor(self) -> Any:
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as error:
                raise ErrorLectura(
                    "PaddleOCR no está instalado: ejecuta uv sync --group ocr en server/."
                ) from error
            self._ocr = PaddleOCR(
                lang=IDIOMA,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        return self._ocr

    def leer(self, contenido: bytes, tipo: TipoArchivo) -> Lectura:
        import numpy as np

        paginas = paginas_de(contenido, tipo)
        textos: list[str] = []
        confianzas: list[float] = []
        with self._bloqueo:
            motor = self._motor()
            for pagina in paginas:
                # PaddleOCR espera BGR, como OpenCV.
                for resultado in motor.predict(np.asarray(pagina)[:, :, ::-1]):
                    for texto, confianza in zip(
                        resultado["rec_texts"], resultado["rec_scores"], strict=True
                    ):
                        if texto.strip():
                            textos.append(texto.strip())
                            confianzas.append(float(confianza))
        media = sum(confianzas) / len(confianzas) if confianzas else 0.0
        return Lectura("\n".join(textos), media, len(paginas))
