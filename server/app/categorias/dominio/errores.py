"""Errores de las categorías. Cada uno trae un código estable para el frontend y un mensaje que dice
qué ocurrió y qué hacer."""

from collections.abc import Mapping
from uuid import UUID


class ErrorCategorias(Exception):
    codigo = "ERROR_CATEGORIAS"
    mensaje = "No pudimos completar la operación con la categoría."

    def __init__(self, mensaje: str | None = None, campos: Mapping[str, str] | None = None) -> None:
        self.mensaje = mensaje or self.mensaje
        self.campos = dict(campos or {})
        super().__init__(self.mensaje)


class CategoriaInvalida(ErrorCategorias):
    codigo = "DATOS_INVALIDOS"
    mensaje = "Revisa los datos marcados."


class CategoriaDuplicada(ErrorCategorias):
    """Ya existe una categoría con ese nombre en el espacio, activa o archivada."""

    codigo = "CATEGORIA_DUPLICADA"

    def __init__(self, nombre: str, categoria_id: UUID | None, archivada: bool) -> None:
        self.categoria_id = categoria_id
        self.archivada = archivada
        mensaje = (
            f"Ya tienes una categoría archivada llamada «{nombre}». "
            "Reactívala para volver a usarla."
            if archivada
            else f"Ya tienes una categoría llamada «{nombre}»."
        )
        super().__init__(mensaje, campos={"nombre": mensaje})


class LimiteCategorias(ErrorCategorias):
    codigo = "LIMITE_CATEGORIAS"

    def __init__(self, maximo: int) -> None:
        super().__init__(
            f"Ya tienes {maximo} categorías activas, el máximo permitido. Archiva alguna que ya "
            "no uses para crear o reactivar otra."
        )


class CategoriaNoEncontrada(ErrorCategorias):
    codigo = "CATEGORIA_NO_ENCONTRADA"
    mensaje = "No encontramos esa categoría en tu espacio."


class CategoriaArchivada(ErrorCategorias):
    codigo = "CATEGORIA_ARCHIVADA"
    mensaje = "Esta categoría está archivada. Reactívala para editarla."


class CategoriaYaArchivada(ErrorCategorias):
    codigo = "CATEGORIA_YA_ARCHIVADA"
    mensaje = "Esta categoría ya está archivada."


class CategoriaNoArchivada(ErrorCategorias):
    codigo = "CATEGORIA_NO_ARCHIVADA"
    mensaje = "Esta categoría ya está activa."


class SinCambios(ErrorCategorias):
    codigo = "SIN_CAMBIOS"
    mensaje = "No hay cambios por guardar: los datos son iguales a los registrados."
