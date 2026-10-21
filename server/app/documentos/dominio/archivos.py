"""Archivos que se aceptan como documento de una deuda.

El tipo se decide por los primeros bytes del archivo, no por su extensión ni por lo que declara el
navegador: un ejecutable renombrado a .pdf no pasa. El nombre original solo se guarda para
mostrarlo, limpio de rutas y de caracteres invisibles.
"""

import re
import unicodedata

from app.documentos.dominio.errores import ArchivoDemasiadoGrande, ArchivoInvalido, ArchivoVacio
from app.documentos.dominio.modelos import TAMANO_MAXIMO, TipoArchivo

LARGO_NOMBRE = 120
# Marcas de una foto HEIC/HEIF (el formato de las cámaras del iPhone), que no se acepta.
MARCAS_HEIC = {b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1"}
HEIC = (
    "Las fotos HEIC del iPhone aún no se aceptan. Compártela como JPG (o toma una captura) y "
    "vuelve a subirla."
)
INVISIBLES = re.compile(r"[\x00-\x1f\x7f-\x9f​-‏‪-‮⁠-⁩﻿]")


def detectar_tipo(contenido: bytes) -> TipoArchivo | None:
    if contenido.startswith(b"%PDF-"):
        return TipoArchivo.PDF
    if contenido.startswith(b"\xff\xd8\xff"):
        return TipoArchivo.JPEG
    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return TipoArchivo.PNG
    if contenido[:4] == b"RIFF" and contenido[8:12] == b"WEBP":
        return TipoArchivo.WEBP
    return None


def validar_archivo(contenido: bytes) -> TipoArchivo:
    if not contenido:
        raise ArchivoVacio()
    if len(contenido) > TAMANO_MAXIMO:
        raise ArchivoDemasiadoGrande()
    tipo = detectar_tipo(contenido)
    if tipo is None:
        if contenido[4:8] == b"ftyp" and contenido[8:12] in MARCAS_HEIC:
            raise ArchivoInvalido(HEIC)
        raise ArchivoInvalido()
    return tipo


def limpiar_nombre(nombre: str | None, tipo: TipoArchivo) -> str:
    """Solo el nombre, sin carpetas ni caracteres invisibles. Sin nombre usable, uno genérico."""
    base = re.split(r"[\\/]", nombre or "")[-1]
    limpio = " ".join(INVISIBLES.sub("", unicodedata.normalize("NFC", base)).split())
    return limpio[:LARGO_NOMBRE] or f"documento.{tipo.extension}"
