"""Incorporación de una cuenta: los pasos obligatorios antes de entrar a su espacio.

El único paso obligatorio es aceptar los términos de uso y la política de privacidad vigentes.
Mientras quede pendiente, la sesión solo sirve para completarlo. Cambiar la contraseña temporal es
recomendado pero no bloquea: la sesión lo informa en `debe_cambiar_contrasena` para recordarlo.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.acceso.dominio.errores import DatosInvalidos, DocumentosDesactualizados

ACEPTACION_INCOMPLETA = "Acepta los términos de uso y la política de privacidad para continuar."


class PasoPendiente(StrEnum):
    ACEPTAR_DOCUMENTOS = "aceptar_documentos"


class TipoDocumentoLegal(StrEnum):
    TERMINOS = "terminos"
    PRIVACIDAD = "privacidad"


@dataclass(frozen=True)
class Seccion:
    titulo: str
    parrafos: tuple[str, ...]


@dataclass(frozen=True)
class DocumentoLegal:
    id: int
    tipo: TipoDocumentoLegal
    version: int
    titulo: str
    resumen: str
    secciones: tuple[Seccion, ...]
    vigente_desde: datetime


@dataclass(frozen=True)
class DocumentoVigente:
    documento: DocumentoLegal
    aceptado_en: datetime | None


def pasos_pendientes(hay_documentos_sin_aceptar: bool) -> tuple[PasoPendiente, ...]:
    """Pasos que faltan, en el orden en que deben completarse."""
    if hay_documentos_sin_aceptar:
        return (PasoPendiente.ACEPTAR_DOCUMENTOS,)
    return ()


def documentos_a_aceptar(
    vigentes: Iterable[DocumentoLegal], aceptados: Mapping[TipoDocumentoLegal, int]
) -> list[DocumentoLegal]:
    """Comprueba que se aceptan exactamente las versiones vigentes de todos los documentos.

    El cliente indica la versión que leyó: si otra se publicó mientras tanto, se rechaza para que
    la persona lea la nueva en vez de aceptarla sin verla.
    """
    documentos = list(vigentes)
    faltantes = [d for d in documentos if d.tipo not in aceptados]
    if faltantes or not documentos:
        raise DatosInvalidos(campos={"documentos": ACEPTACION_INCOMPLETA})
    if any(aceptados[d.tipo] != d.version for d in documentos):
        raise DocumentosDesactualizados()
    return documentos
