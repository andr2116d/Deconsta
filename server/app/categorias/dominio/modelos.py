"""Categorías del espacio: agrupan las deudas (agua, luz, tarjetas…) para filtrarlas, resumirlas y
exportarlas.

Pertenecen al espacio del gerente y las comparte todo su equipo. El nombre es único dentro del
espacio sin distinguir mayúsculas, tildes ni espacios repetidos. Nunca se borran: una categoría
archivada deja de ofrecerse para deudas nuevas, pero las deudas que ya la usan la conservan.
"""

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.categorias.dominio.errores import (
    CategoriaArchivada,
    CategoriaInvalida,
    CategoriaNoArchivada,
    CategoriaYaArchivada,
    SinCambios,
)

MAXIMO_CATEGORIAS_ACTIVAS = 50
LARGO_MINIMO_NOMBRE = 2
LARGO_MAXIMO_NOMBRE = 40
LARGO_MAXIMO_DESCRIPCION = 200
# Además de letras, números y espacios: «Agua y desagüe», «Luz (oficina)», «Teléfono/internet».
SIGNOS_NOMBRE = set(" .,&/()'+-")


class Color(StrEnum):
    CIRUELA = "ciruela"
    CORAL = "coral"
    AMBAR = "ambar"
    OLIVA = "oliva"
    VERDE = "verde"
    AZUL = "azul"
    LAVANDA = "lavanda"
    GRAFITO = "grafito"


class Icono(StrEnum):
    AGUA = "agua"
    LUZ = "luz"
    GAS = "gas"
    TELEFONO = "telefono"
    INTERNET = "internet"
    TARJETA = "tarjeta"
    BANCO = "banco"
    IMPUESTOS = "impuestos"
    VIVIENDA = "vivienda"
    TRANSPORTE = "transporte"
    SALUD = "salud"
    EDUCACION = "educacion"
    SEGURO = "seguro"
    ETIQUETA = "etiqueta"


def limpiar_texto(valor: str) -> str:
    """Forma en que se guarda: NFKC, sin espacios en los extremos y con espacios simples."""
    return " ".join(unicodedata.normalize("NFKC", valor).split())


def clave_nombre(nombre: str) -> str:
    """Forma para comparar nombres: minúsculas, sin tildes y con espacios simples."""
    descompuesto = unicodedata.normalize("NFKD", limpiar_texto(nombre).casefold())
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def _error_nombre(nombre: str) -> str | None:
    if not nombre:
        return "Escribe el nombre de la categoría."
    if not LARGO_MINIMO_NOMBRE <= len(nombre) <= LARGO_MAXIMO_NOMBRE:
        return f"Usa de {LARGO_MINIMO_NOMBRE} a {LARGO_MAXIMO_NOMBRE} caracteres."
    if not nombre[0].isalnum() or not any(c.isalpha() for c in nombre):
        return "Empieza con una letra o un número e incluye al menos una letra."
    if any(not (c.isalnum() or c in SIGNOS_NOMBRE) for c in nombre):
        return "Usa solo letras, números, espacios y los signos . , & / ( ) ' + -"
    return None


@dataclass(frozen=True)
class DatosCategoria:
    nombre: str
    descripcion: str | None
    color: Color
    icono: Icono

    @classmethod
    def crear(
        cls, *, nombre: str, descripcion: str | None, color: str, icono: str
    ) -> "DatosCategoria":
        """Valida y normaliza los datos. Reúne los errores de todos los campos en uno solo."""
        nombre = limpiar_texto(nombre)
        descripcion = limpiar_texto(descripcion or "") or None
        errores: dict[str, str] = {}
        if mensaje := _error_nombre(nombre):
            errores["nombre"] = mensaje
        if descripcion and len(descripcion) > LARGO_MAXIMO_DESCRIPCION:
            errores["descripcion"] = f"Usa como máximo {LARGO_MAXIMO_DESCRIPCION} caracteres."
        if color not in Color:
            errores["color"] = "Elige uno de los colores disponibles."
        if icono not in Icono:
            errores["icono"] = "Elige uno de los íconos disponibles."
        if errores:
            raise CategoriaInvalida(campos=errores)
        return cls(nombre, descripcion, Color(color), Icono(icono))

    @property
    def clave(self) -> str:
        return clave_nombre(self.nombre)


@dataclass
class Categoria:
    id: UUID
    gerente_id: UUID
    nombre: str
    descripcion: str | None
    color: Color
    icono: Icono
    creado_por: UUID
    creado_en: datetime
    actualizado_en: datetime
    archivado_en: datetime | None = None

    @property
    def archivada(self) -> bool:
        return self.archivado_en is not None

    @property
    def clave(self) -> str:
        return clave_nombre(self.nombre)

    def datos(self) -> DatosCategoria:
        return DatosCategoria(self.nombre, self.descripcion, self.color, self.icono)

    def exigir_activa(self) -> None:
        """Una categoría archivada no se edita: primero se reactiva."""
        if self.archivada:
            raise CategoriaArchivada()

    def editar(self, datos: DatosCategoria, ahora: datetime) -> dict[str, Any]:
        """Aplica los datos nuevos y devuelve los cambios (antes y después) para la auditoría."""
        self.exigir_activa()
        actual = self.datos()
        cambios = {
            campo: {"antes": getattr(actual, campo), "despues": getattr(datos, campo)}
            for campo in ("nombre", "descripcion", "color", "icono")
            if getattr(actual, campo) != getattr(datos, campo)
        }
        if not cambios:
            raise SinCambios()
        self.nombre, self.descripcion = datos.nombre, datos.descripcion
        self.color, self.icono = datos.color, datos.icono
        self.actualizado_en = ahora
        return cambios

    def archivar(self, ahora: datetime) -> None:
        if self.archivada:
            raise CategoriaYaArchivada()
        self.archivado_en = ahora
        self.actualizado_en = ahora

    def reactivar(self, ahora: datetime) -> None:
        if not self.archivada:
            raise CategoriaNoArchivada()
        self.archivado_en = None
        self.actualizado_en = ahora
