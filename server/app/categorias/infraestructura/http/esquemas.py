from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.acceso.infraestructura.http.esquemas import exigir
from app.categorias.aplicacion.categorias import NuevaCategoria
from app.categorias.dominio.modelos import Categoria, Color, Icono


class CategoriaEntrada(BaseModel):
    # Los topes son holgados: el dominio da el mensaje preciso de cada regla.
    nombre: str = Field("", max_length=200, validate_default=True)
    descripcion: str | None = Field(None, max_length=1000)
    color: str | None = Field(None, max_length=20)
    icono: str | None = Field(None, max_length=20)

    @field_validator("nombre")
    @classmethod
    def validar_nombre(cls, valor: str) -> str:
        return exigir(valor, "Escribe el nombre de la categoría.")

    def nueva(self) -> NuevaCategoria:
        return NuevaCategoria(self.nombre, self.descripcion, self.color, self.icono)


class CategoriaSalida(BaseModel):
    id: UUID
    nombre: str
    descripcion: str | None
    color: Color
    icono: Icono
    archivada: bool
    creado_en: datetime
    actualizado_en: datetime
    archivado_en: datetime | None

    @classmethod
    def desde(cls, categoria: Categoria) -> "CategoriaSalida":
        return cls(
            id=categoria.id,
            nombre=categoria.nombre,
            descripcion=categoria.descripcion,
            color=categoria.color,
            icono=categoria.icono,
            archivada=categoria.archivada,
            creado_en=categoria.creado_en,
            actualizado_en=categoria.actualizado_en,
            archivado_en=categoria.archivado_en,
        )
