from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.categorias.dominio.errores import (
    CategoriaArchivada,
    CategoriaInvalida,
    CategoriaNoArchivada,
    CategoriaYaArchivada,
    SinCambios,
)
from app.categorias.dominio.modelos import Categoria, Color, DatosCategoria, Icono, clave_nombre

AHORA = datetime(2026, 10, 21, tzinfo=UTC)


def datos(**cambios: str | None) -> DatosCategoria:
    valores: dict[str, str | None] = {
        "nombre": "Luz",
        "descripcion": None,
        "color": "ambar",
        "icono": "luz",
    }
    valores.update(cambios)
    return DatosCategoria.crear(**valores)  # type: ignore[arg-type]


def categoria() -> Categoria:
    return Categoria(
        id=uuid4(),
        gerente_id=uuid4(),
        nombre="Luz",
        descripcion=None,
        color=Color.AMBAR,
        icono=Icono.LUZ,
        creado_por=uuid4(),
        creado_en=AHORA,
        actualizado_en=AHORA,
    )


def test_el_nombre_se_compara_sin_mayusculas_tildes_ni_espacios_repetidos() -> None:
    assert clave_nombre("  Teléfono   e  INTERNET ") == clave_nombre("telefono e internet")
    assert clave_nombre("Agua") != clave_nombre("Agua y desagüe")


def test_guarda_el_nombre_y_la_descripcion_sin_espacios_sobrantes() -> None:
    creados = datos(nombre="  Agua   y desagüe ", descripcion="   ")
    assert creados.nombre == "Agua y desagüe"
    assert creados.descripcion is None


@pytest.mark.parametrize(
    ("cambios", "campo", "mensaje"),
    [
        ({"nombre": "   "}, "nombre", "Escribe el nombre de la categoría."),
        ({"nombre": "L"}, "nombre", "Usa de 2 a 40 caracteres."),
        ({"nombre": "x" * 41}, "nombre", "Usa de 2 a 40 caracteres."),
        ({"nombre": "123"}, "nombre", "incluye al menos una letra"),
        ({"nombre": "Luz <b>"}, "nombre", "Usa solo letras, números"),
        ({"descripcion": "x" * 201}, "descripcion", "Usa como máximo 200 caracteres."),
        ({"color": "fucsia"}, "color", "Elige uno de los colores disponibles."),
        ({"icono": "cohete"}, "icono", "Elige uno de los íconos disponibles."),
    ],
)
def test_rechaza_datos_invalidos_con_un_mensaje_por_campo(
    cambios: dict[str, str], campo: str, mensaje: str
) -> None:
    with pytest.raises(CategoriaInvalida) as error:
        datos(**cambios)
    assert mensaje in error.value.campos[campo]


def test_editar_registra_solo_lo_que_cambia_y_rechaza_si_no_hay_cambios() -> None:
    luz = categoria()
    cambios = luz.editar(datos(nombre="Luz de la oficina"), AHORA)
    assert cambios == {"nombre": {"antes": "Luz", "despues": "Luz de la oficina"}}

    with pytest.raises(SinCambios):
        luz.editar(datos(nombre="Luz de la oficina"), AHORA)


def test_una_categoria_archivada_no_se_edita_hasta_reactivarla() -> None:
    luz = categoria()
    luz.archivar(AHORA)
    with pytest.raises(CategoriaArchivada):
        luz.editar(datos(nombre="Electricidad"), AHORA)
    with pytest.raises(CategoriaYaArchivada):
        luz.archivar(AHORA)

    luz.reactivar(AHORA)
    assert not luz.archivada
    with pytest.raises(CategoriaNoArchivada):
        luz.reactivar(AHORA)
