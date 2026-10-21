"""Reglas del análisis de un documento, en sus tres capas.

1. Lectura (OCR): si el texto no se lee, el documento es ilegible y no se registra: no hay forma
   de comprobar a qué gasto corresponde. De su texto salen además los números largos que
   identifican el documento aunque no se haya podido armar su clave de negocio.
2. Revisión con IA: propone los datos y da un veredicto. Sus datos se contrastan con el texto
   leído: un importe o un código que no aparece en el documento no se da por bueno.
3. Metadatos: el programa con que se guardó el archivo y si se modificó después de generarse.

Cada hallazgo es una señal con su riesgo. Con riesgo alto, lo que sube una asistente se rechaza;
con riesgo medio, la deuda espera la autorización del gerente. Al gerente solo se le advierte.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.acceso.dominio.modelos import Rol
from app.documentos.dominio.modelos import (
    Analisis,
    Capa,
    DatosLeidos,
    EstadoDocumento,
    Lectura,
    Riesgo,
    Senal,
    TipoDocumento,
)
from app.reglas.dominio.titulares import clave_nombre

# Un recibo legible tiene al menos unas decenas de letras y números leídos con confianza.
MINIMO_CARACTERES = 30
CONFIANZA_MINIMA = 0.70
# Dos documentos con casi los mismos números largos son el mismo documento.
SIMILITUD_REPETIDO = 0.85
MINIMO_NUMEROS_COMUNES = 4

PATRON_IMPORTE = re.compile(r"(?<![\d.,])(\d{1,3}(?:[,.\s]\d{3})+|\d+)[.,](\d{2})(?!\d)")
PATRON_NUMERO_LARGO = re.compile(r"\d{6,}")

# Programas con los que se cambia el contenido de una imagen o se arma un documento desde cero.
EDITORES_IMAGEN = (
    "photoshop", "gimp", "canva", "picsart", "pixlr", "photopea", "affinity", "illustrator",
    "inkscape", "corel", "fotor", "paint.net",
)  # fmt: skip
# Retocan fotos (recortar, enderezar, aclarar) sin ser editores de texto.
RETOQUE_FOTOS = ("lightroom", "snapseed", "vsco", "facetune")
EDITORES_PDF = (
    "sejda", "ilovepdf", "smallpdf", "pdfescape", "pdf-xchange editor", "phantompdf",
    "foxit pdf editor", "pdffiller", "dochub", "nitro pro", "pdfelement", "acrobat pro",
)  # fmt: skip
PROCESADORES_TEXTO = ("microsoft word", "libreoffice writer", "google docs", "pages", "wps")


@dataclass(frozen=True)
class Metadatos:
    """Datos del archivo, no de su contenido."""

    # Software (EXIF de una imagen) o Producer y Creator (PDF).
    programas: tuple[str, ...] = ()
    creado_en: datetime | None = None
    modificado_en: datetime | None = None
    # Secciones de un PDF: más de una indica cambios guardados después de generarlo.
    revisiones: int = 1
    firmado: bool = False
    con_javascript: bool = False


def _senal(capa: Capa, codigo: str, detalle: str, riesgo: Riesgo) -> Senal:
    return Senal(capa, codigo, detalle, riesgo)


def senal_ilegible() -> Senal:
    return _senal(
        Capa.LECTURA,
        "DOCUMENTO_ILEGIBLE",
        "No pudimos leer el documento. Sube una foto nítida, completa y con buena luz, o el PDF "
        "original.",
        Riesgo.ALTO,
    )


def senal_legibilidad(lectura: Lectura) -> Senal | None:
    caracteres = sum(c.isalnum() for c in lectura.texto)
    if caracteres >= MINIMO_CARACTERES and lectura.confianza >= CONFIANZA_MINIMA:
        return None
    return senal_ilegible()


def importes_en_texto(texto: str) -> set[Decimal]:
    """Importes con dos decimales escritos como en Perú («1,182.40») o con coma decimal."""
    importes = set()
    for entero, decimales in PATRON_IMPORTE.findall(texto):
        sin_separadores = re.sub(r"[,.\s]", "", entero)
        importes.add(Decimal(f"{sin_separadores}.{decimales}"))
    return importes


def _alfanumerico(valor: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", valor.upper())


def contrastar(datos: DatosLeidos, lectura: Lectura) -> list[Senal]:
    """Lo que propone la IA debe estar escrito en el documento."""
    senales: list[Senal] = []
    importes = importes_en_texto(lectura.texto)
    esperados = {c.importe for c in datos.cuotas} or ({datos.importe} if datos.importe else set())
    if esperados and not esperados <= importes:
        senales.append(
            _senal(
                Capa.IA,
                "IMPORTE_NO_CONFIRMADO",
                "El importe propuesto no aparece tal cual en el texto del documento.",
                Riesgo.MEDIO,
            )
        )
    codigo = _alfanumerico(datos.codigo_pago or "")
    if codigo and codigo not in _alfanumerico(lectura.texto):
        senales.append(
            _senal(
                Capa.IA,
                "CODIGO_NO_CONFIRMADO",
                "El código de pago propuesto no aparece en el texto del documento.",
                Riesgo.MEDIO,
            )
        )
    return senales


def senal_veredicto(veredicto: str, motivos: Iterable[str]) -> Senal | None:
    detalle = " ".join(m.strip().rstrip(".") + "." for m in motivos if m.strip())
    if veredicto == "alterado":
        return _senal(
            Capa.IA,
            "POSIBLE_ALTERACION",
            detalle or "El documento muestra señales claras de haber sido alterado.",
            Riesgo.ALTO,
        )
    if veredicto == "dudoso":
        return _senal(
            Capa.IA,
            "AUTENTICIDAD_DUDOSA",
            detalle or "No pudimos confirmar que el documento sea auténtico.",
            Riesgo.MEDIO,
        )
    return None


def senal_revision_incompleta() -> Senal:
    return _senal(
        Capa.IA,
        "REVISION_INCOMPLETA",
        "No pudimos completar la revisión automática del documento. Completa los datos a mano.",
        Riesgo.MEDIO,
    )


def _contiene(programa: str, nombres: Iterable[str]) -> str | None:
    """El primer nombre que aparece como palabra completa: «Pages» sí, «WebPages Builder» no."""
    minusculas = programa.casefold()
    return next((n for n in nombres if re.search(rf"\b{re.escape(n)}\b", minusculas)), None)


def evaluar_metadatos(metadatos: Metadatos) -> list[Senal]:
    senales: list[Senal] = []
    for programa in metadatos.programas:
        if _contiene(programa, EDITORES_IMAGEN):
            senales.append(
                _senal(
                    Capa.METADATOS,
                    "EDITOR_DE_IMAGENES",
                    f"El archivo se guardó con {programa}, un programa que permite cambiar el "
                    "contenido del documento.",
                    Riesgo.ALTO,
                )
            )
        elif _contiene(programa, EDITORES_PDF) or _contiene(programa, RETOQUE_FOTOS):
            senales.append(
                _senal(
                    Capa.METADATOS,
                    "EDITADO_DESPUES",
                    f"El archivo pasó por {programa} después de generarse.",
                    Riesgo.MEDIO,
                )
            )
        elif _contiene(programa, PROCESADORES_TEXTO):
            senales.append(
                _senal(
                    Capa.METADATOS,
                    "CREADO_EN_PROCESADOR",
                    f"El documento se creó en {programa}, no en el sistema de un emisor.",
                    Riesgo.MEDIO,
                )
            )
    if metadatos.revisiones > 1 and not metadatos.firmado:
        senales.append(
            _senal(
                Capa.METADATOS,
                "PDF_MODIFICADO",
                "El PDF tiene cambios guardados después de generarse.",
                Riesgo.MEDIO,
            )
        )
    if metadatos.con_javascript:
        senales.append(
            _senal(
                Capa.METADATOS,
                "CONTENIDO_ACTIVO",
                "El PDF trae código que se ejecuta al abrirlo, algo que un recibo no necesita.",
                Riesgo.MEDIO,
            )
        )
    creado, modificado = metadatos.creado_en, metadatos.modificado_en
    if creado and modificado and modificado - creado > timedelta(minutes=10):
        senales.append(
            _senal(
                Capa.METADATOS,
                "FECHA_MODIFICACION_POSTERIOR",
                "El archivo se modificó después de la fecha en que se creó.",
                Riesgo.BAJO,
            )
        )
    return senales


def normalizar_numero(valor: str | None) -> str:
    """Mayúsculas, solo letras y números, y sin ceros a la izquierda en cada grupo numérico:
    «S001-00451236» y «s001 451236» son el mismo número, como «5487 1236» y «54871236»."""
    grupos = re.findall(r"[0-9A-Z]+", (valor or "").upper())
    return "".join(g.lstrip("0") or "0" if g.isdigit() else g for g in grupos)


def clave_negocio(datos: DatosLeidos) -> str | None:
    """Lo que identifica al documento aunque se escanee o fotografíe otra vez: el emisor y el
    número que le da su emisor. Sin esos datos no hay clave."""
    emisor = normalizar_numero(datos.emisor_ruc) or clave_nombre(datos.emisor or "")
    if not emisor:
        return None
    numero = normalizar_numero(datos.numero_documento)
    codigo = normalizar_numero(datos.codigo_pago)
    if datos.tipo in (TipoDocumento.BOLETA, TipoDocumento.FACTURA):
        partes = [numero]
    elif datos.tipo is TipoDocumento.RECIBO_SERVICIO:
        partes = [codigo, normalizar_numero(datos.periodo) or numero]
    elif datos.tipo is TipoDocumento.CRONOGRAMA:
        partes = [codigo or numero]
    else:
        partes = [numero]
    if not all(partes):
        return None
    return "|".join([datos.tipo.value, emisor, *partes])


def numeros_largos(texto: str) -> set[str]:
    """Números de 6 dígitos o más: suministros, números de recibo, operaciones, RUC."""
    return {n.lstrip("0") for n in PATRON_NUMERO_LARGO.findall(texto)} - {""}


def mismos_numeros(propios: set[bytes], ajenos: set[bytes]) -> bool:
    comunes = propios & ajenos
    if len(comunes) < MINIMO_NUMEROS_COMUNES:
        return False
    return len(comunes) / len(propios | ajenos) >= SIMILITUD_REPETIDO


def estado_tras_analisis(analisis: Analisis, rol: Rol) -> EstadoDocumento:
    """Con riesgo alto, lo de una asistente no se registra; al gerente solo se le advierte."""
    if rol is Rol.ASISTENTE and analisis.riesgo is Riesgo.ALTO:
        return EstadoDocumento.RECHAZADO
    return EstadoDocumento.LISTO
