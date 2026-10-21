from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.categorias.dominio.errores import (
    CategoriaArchivada,
    CategoriaDuplicada,
    CategoriaInvalida,
    CategoriaNoArchivada,
    CategoriaNoEncontrada,
    CategoriaYaArchivada,
    ErrorCategorias,
    LimiteCategorias,
    SinCambios,
)
from app.core.errores import respuesta_error

ESTADOS_HTTP: dict[type[ErrorCategorias], int] = {
    CategoriaNoEncontrada: 404,
    CategoriaDuplicada: 409,
    LimiteCategorias: 409,
    CategoriaArchivada: 409,
    CategoriaYaArchivada: 409,
    CategoriaNoArchivada: 409,
    CategoriaInvalida: 422,
    SinCambios: 422,
}


async def manejar_error_categorias(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ErrorCategorias)
    extra: dict[str, object] = {}
    if isinstance(exc, CategoriaDuplicada) and exc.categoria_id is not None:
        # Permite ofrecer la reactivación de la categoría archivada con ese nombre.
        extra["existing_category"] = {"id": str(exc.categoria_id), "archivada": exc.archivada}
    return respuesta_error(
        ESTADOS_HTTP.get(type(exc), 400), exc.codigo, exc.mensaje, campos=exc.campos, extra=extra
    )


def registrar_manejadores_categorias(app: FastAPI) -> None:
    app.add_exception_handler(ErrorCategorias, manejar_error_categorias)
