from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.acceso.dominio import politica_contrasena
from app.acceso.dominio.datos_personales import DatosPersonales
from app.acceso.dominio.errores import DatosInvalidos
from app.acceso.dominio.modelos import MAXIMO_INTENTOS_FALLIDOS, Rol, Usuario

AHORA = datetime(2026, 10, 21, tzinfo=UTC)


def usuario(rol: Rol) -> Usuario:
    return Usuario(
        id=uuid4(),
        rol=rol,
        gerente_id=None if rol is Rol.GERENTE else uuid4(),
        nombre_usuario="lucia.vega",
        nombres="Lucía",
        contrasena_hash="x",
        debe_cambiar_contrasena=True,
        contrasena_actualizada_en=AHORA,
        ultimo_ingreso_en=None,
        intentos_fallidos=0,
        bloqueada_en=None,
    )


def test_la_asistente_se_bloquea_exactamente_al_llegar_al_maximo() -> None:
    asistente = usuario(Rol.ASISTENTE)
    resultados = [
        asistente.registrar_intento_fallido(AHORA) for _ in range(MAXIMO_INTENTOS_FALLIDOS)
    ]

    assert resultados == [False] * (MAXIMO_INTENTOS_FALLIDOS - 1) + [True]
    assert asistente.bloqueada
    # Los intentos sobre una cuenta ya bloqueada no la vuelven a bloquear ni suman.
    assert asistente.registrar_intento_fallido(AHORA) is False
    assert asistente.intentos_fallidos == MAXIMO_INTENTOS_FALLIDOS


def test_el_gerente_nunca_queda_bloqueado() -> None:
    gerente = usuario(Rol.GERENTE)
    assert not any(gerente.registrar_intento_fallido(AHORA) for _ in range(20))
    assert not gerente.bloqueada


def test_desbloquear_y_cambiar_contrasena_actualizan_los_indicadores() -> None:
    asistente = usuario(Rol.ASISTENTE)
    for _ in range(MAXIMO_INTENTOS_FALLIDOS):
        asistente.registrar_intento_fallido(AHORA)
    asistente.desbloquear()
    asistente.cambiar_contrasena("nuevo", AHORA)

    assert (asistente.bloqueada, asistente.intentos_fallidos) == (False, 0)
    assert asistente.debe_cambiar_contrasena is False


@pytest.mark.parametrize(
    ("contrasena", "incumplidos"),
    [
        ("Ciruela-Rosa-2026", set()),
        ("corta1", {"LONGITUD_MINIMA"}),
        ("soloLetrasLargas", {"SIN_NUMERO"}),
        ("12345678901", {"SIN_LETRA"}),
        ("password123", {"COMUN"}),
        ("lucia.vega2026", {"CONTIENE_USUARIO"}),
        (" Espacio-2026 ", {"ESPACIOS_EXTREMOS"}),
        ("Ab3-" * 33, {"LONGITUD_MAXIMA"}),
    ],
)
def test_politica_de_contrasenas(contrasena: str, incumplidos: set[str]) -> None:
    resultado = politica_contrasena.evaluar(contrasena, nombre_usuario="Lucia.Vega")
    assert set(resultado) == incumplidos


@pytest.mark.parametrize(
    ("tipo", "numero", "normalizado"),
    [("DNI", "4567 8912", "45678912"), ("ce", "ab-1234567", "AB1234567")],
)
def test_acepta_dni_y_carne_de_extranjeria(tipo: str, numero: str, normalizado: str) -> None:
    datos = DatosPersonales.crear(
        nombres=" Lucía ",
        apellidos="Vega",
        correo="Lucia@Ejemplo.PE",
        tipo_documento=tipo,
        numero_documento=numero,
    )
    assert datos.numero_documento == normalizado
    assert (datos.nombres, datos.correo, datos.telefono) == ("Lucía", "lucia@ejemplo.pe", None)


def test_rechaza_datos_personales_invalidos_por_campo() -> None:
    with pytest.raises(DatosInvalidos) as error:
        DatosPersonales.crear(
            nombres="",
            apellidos="V3ga",
            correo="no-es-correo",
            tipo_documento="dni",
            numero_documento="123",
            telefono="12",
        )
    assert set(error.value.campos) == {
        "nombres",
        "apellidos",
        "correo",
        "numero_documento",
        "telefono",
    }
