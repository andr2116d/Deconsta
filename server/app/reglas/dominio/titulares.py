"""Titulares de los recibos: quiénes aparecen como «titular» o «cliente» en un documento y cómo
se reconoce que son la misma persona.

En los recibos peruanos el titular aparece de formas distintas: «TORRES RIOS DANIELA M» en un
recibo de luz, «Daniela Torres Ríos» en un estado de cuenta, solo con su DNI en una boleta de más
de S/ 700 o con un RUC 10 (persona natural con negocio), que contiene su DNI. Por eso se comparan
primero los documentos y, si falta alguno, los nombres sin importar orden, tildes, mayúsculas,
partículas («de», «la») ni iniciales.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.reglas.dominio.errores import ReglaInvalida

MAXIMO_TITULARES = 20
LARGO_NOMBRE = (3, 120)
LARGO_RELACION = 40
# Personas y razones sociales: «María de los Ángeles Ruiz», «Inversiones Ruiz & Cía. S.A.C.».
PATRON_NOMBRE = re.compile(r"^[^\W_][\w .,&'’()/-]*$")
PARTICULAS = frozenset({"de", "del", "la", "las", "los", "y", "e", "da", "van", "von"})
# RUC: 10 (persona natural), 15, 16, 17 (otros) o 20 (persona jurídica), con dígito verificador.
PATRON_RUC = re.compile(r"^(10|15|16|17|20)\d{9}$")
PESOS_RUC = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


class TipoDocumentoTitular(StrEnum):
    DNI = "dni"
    CARNE_EXTRANJERIA = "ce"
    RUC = "ruc"


def limpiar(valor: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", valor).split())


def palabras(nombre: str) -> list[str]:
    """Palabras comparables de un nombre: sin tildes, mayúsculas, signos ni partículas."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", nombre.casefold()) if not unicodedata.combining(c)
    )
    return [p for p in re.split(r"[^a-z0-9ñ]+", sin_tildes) if p and p not in PARTICULAS]


def clave_nombre(nombre: str) -> str:
    """Forma única de un nombre sin importar el orden de sus palabras."""
    return " ".join(sorted(palabras(nombre)))


def ruc_valido(ruc: str) -> bool:
    if not PATRON_RUC.match(ruc):
        return False
    resto = 11 - sum(int(d) * p for d, p in zip(ruc[:10], PESOS_RUC, strict=True)) % 11
    return int(ruc[10]) == {10: 0, 11: 1}.get(resto, resto)


def normalizar_documento(numero: str) -> str:
    return re.sub(r"[\s.-]", "", numero).upper()


def _error_documento(tipo: TipoDocumentoTitular, numero: str) -> str | None:
    if tipo is TipoDocumentoTitular.DNI and not re.fullmatch(r"\d{8}", numero):
        return "El DNI debe tener 8 dígitos."
    if tipo is TipoDocumentoTitular.CARNE_EXTRANJERIA and not re.fullmatch(
        r"[A-Z0-9]{9,12}", numero
    ):
        return "El carné de extranjería debe tener entre 9 y 12 letras o dígitos."
    if tipo is TipoDocumentoTitular.RUC and not ruc_valido(numero):
        return "El RUC debe tener 11 dígitos válidos y empezar con 10, 15, 16, 17 o 20."
    return None


@dataclass(frozen=True)
class Documento:
    tipo: TipoDocumentoTitular
    numero: str

    def coincide(self, otro: "Documento") -> bool:
        """El mismo documento, o un RUC 10 que contiene ese DNI."""
        if (self.tipo, self.numero) == (otro.tipo, otro.numero):
            return True
        dni, ruc = (self, otro) if self.tipo is TipoDocumentoTitular.DNI else (otro, self)
        return (
            dni.tipo is TipoDocumentoTitular.DNI
            and ruc.tipo is TipoDocumentoTitular.RUC
            and ruc.numero.startswith("10")
            and ruc.numero[2:10] == dni.numero
        )


def documento_de(tipo: str | None, numero: str | None, errores: dict[str, str]) -> Documento | None:
    """Documento opcional: sin tipo ni número no hay documento; con uno solo, falta el otro."""
    numero = (numero or "").strip()
    if not tipo and not numero:
        return None
    if tipo is None or tipo not in TipoDocumentoTitular:
        errores["tipo_documento"] = "Elige DNI, carné de extranjería o RUC."
        return None
    tipo_documento = TipoDocumentoTitular(tipo)
    normalizado = normalizar_documento(numero)
    if not normalizado:
        errores["numero_documento"] = "Escribe el número de documento o quita el tipo."
        return None
    if mensaje := _error_documento(tipo_documento, normalizado):
        errores["numero_documento"] = mensaje
        return None
    return Documento(tipo_documento, normalizado)


def _error_nombre(nombre: str) -> str | None:
    minimo, maximo = LARGO_NOMBRE
    if not nombre:
        return "Escribe el nombre como aparece en sus recibos."
    if not minimo <= len(nombre) <= maximo or not PATRON_NOMBRE.match(nombre):
        return f"Usa de {minimo} a {maximo} letras, números, espacios y los signos . , & ' ( ) / -"
    if len(palabras(nombre)) < 2:
        return "Escribe al menos un nombre y un apellido, o la razón social completa."
    return None


def validar_nombre(nombre: str, errores: dict[str, str]) -> str:
    limpio = limpiar(nombre)
    if mensaje := _error_nombre(limpio):
        errores["nombre"] = mensaje
    return limpio


def validar_relacion(relacion: str | None, errores: dict[str, str]) -> str | None:
    limpia = limpiar(relacion or "") or None
    if limpia and (len(limpia) > LARGO_RELACION or not PATRON_NOMBRE.match(limpia)):
        errores["relacion"] = f"Usa hasta {LARGO_RELACION} letras, por ejemplo «Esposa»."
    return limpia


@dataclass(frozen=True)
class DatosTitular:
    nombre: str
    documento: Documento | None
    relacion: str | None

    @classmethod
    def crear(
        cls,
        *,
        nombre: str,
        tipo_documento: str | None,
        numero_documento: str | None,
        relacion: str | None,
    ) -> "DatosTitular":
        """Valida y normaliza. Reúne los errores de todos los campos en uno solo."""
        errores: dict[str, str] = {}
        limpio = validar_nombre(nombre, errores)
        documento = documento_de(tipo_documento, numero_documento, errores)
        relacion_limpia = validar_relacion(relacion, errores)
        if errores:
            raise ReglaInvalida(campos=errores)
        return cls(limpio, documento, relacion_limpia)


@dataclass
class TitularAutorizado:
    id: UUID
    gerente_id: UUID
    nombre: str
    documento: Documento | None
    relacion: str | None
    autorizacion_declarada_en: datetime
    creado_por: UUID
    creado_en: datetime
    actualizado_en: datetime
    quitado_en: datetime | None = None

    @property
    def quitado(self) -> bool:
        return self.quitado_en is not None


def nombres_coinciden(uno: str, otro: str) -> bool:
    """Las palabras del nombre más corto están todas en el más largo, en cualquier orden. Una
    inicial («M») vale por una palabra que empieza con ella. Hacen falta al menos dos palabras
    completas: un solo nombre o apellido no identifica a nadie."""
    corto, largo = sorted((palabras(uno), palabras(otro)), key=len)
    if sum(len(p) > 1 for p in corto) < 2:
        return False
    disponibles = list(largo)
    # Primero las palabras completas, para que una inicial no tome la palabra de otra.
    for palabra in sorted(corto, key=len, reverse=True):
        encontrada = next(
            (
                d
                for d in disponibles
                if d == palabra or (len(palabra) == 1 and d.startswith(palabra))
            ),
            None,
        )
        if encontrada is None:
            return False
        disponibles.remove(encontrada)
    return True
