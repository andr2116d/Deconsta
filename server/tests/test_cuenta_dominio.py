from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.acceso.dominio.cuenta import CupoNombreUsuario, periodo_mensual, revisar_cambios
from app.acceso.dominio.datos_personales import DatosPersonales, validar_cargo
from app.acceso.dominio.errores import (
    CambioDocumentoSinConfirmar,
    DatosInvalidos,
    DocumentoNoModificable,
    SinCambios,
    SinPermiso,
)
from app.acceso.dominio.modelos import Rol

LIMA = ZoneInfo("America/Lima")


def persona(**cambios: str | None) -> DatosPersonales:
    valores: dict[str, str | None] = {
        "nombres": "Valentina",
        "apellidos": "Ramos Díaz",
        "correo": "valentina@ejemplo.pe",
        "tipo_documento": "dni",
        "numero_documento": "45678912",
        "telefono": "987654321",
        "nombre_recibos": None,
    }
    valores.update(cambios)
    return DatosPersonales.crear(**valores)  # type: ignore[arg-type]


def revisar(nuevos: DatosPersonales, rol: Rol = Rol.GERENTE, confirmar: bool = False):
    return revisar_cambios(persona(), nuevos, rol=rol, confirmar_documento=confirmar)


def test_el_mes_se_cuenta_en_la_hora_de_lima() -> None:
    # 04:30 UTC del 1 de noviembre todavía es 31 de octubre en Lima.
    inicio, siguiente = periodo_mensual(datetime(2026, 11, 1, 4, 30, tzinfo=UTC), LIMA)
    assert (inicio.year, inicio.month, inicio.day, inicio.hour) == (2026, 10, 1, 0)
    assert (siguiente.month, siguiente.day) == (11, 1)
    assert siguiente.utcoffset() == LIMA.utcoffset(siguiente)


def test_diciembre_renueva_en_enero_del_anio_siguiente() -> None:
    _, siguiente = periodo_mensual(datetime(2026, 12, 15, tzinfo=UTC), LIMA)
    assert (siguiente.year, siguiente.month, siguiente.day) == (2027, 1, 1)


def test_el_cupo_no_baja_de_cero() -> None:
    assert CupoNombreUsuario(usados=5, renueva_en=datetime.now(UTC)).restantes == 0


def test_espacios_y_mayusculas_no_cuentan_como_cambio() -> None:
    with pytest.raises(SinCambios):
        revisar(
            persona(nombres="  Valentina ", correo="VALENTINA@ejemplo.pe ", telefono="987 654 321")
        )


def test_cambiar_el_telefono_no_pide_contrasena() -> None:
    cambios = revisar(persona(telefono="912345678"))
    assert cambios.campos == ("telefono",)
    assert not cambios.requiere_contrasena


def test_cambiar_el_correo_pide_contrasena() -> None:
    assert revisar(persona(correo="nuevo@ejemplo.pe")).requiere_contrasena


def test_el_numero_de_documento_no_se_cambia() -> None:
    with pytest.raises(DocumentoNoModificable):
        revisar(persona(numero_documento="45678913"))


def test_pasar_de_dni_a_carne_exige_confirmacion() -> None:
    carne = persona(tipo_documento="ce", numero_documento="001234567")
    with pytest.raises(CambioDocumentoSinConfirmar):
        revisar(carne)
    cambios = revisar(carne, confirmar=True)
    assert cambios.cambia_documento and cambios.requiere_contrasena


def test_no_se_pasa_de_carne_a_dni() -> None:
    carne = persona(tipo_documento="ce", numero_documento="001234567")
    with pytest.raises(DocumentoNoModificable):
        revisar_cambios(carne, persona(), rol=Rol.GERENTE, confirmar_documento=True)


def test_solo_el_gerente_tiene_nombre_en_recibos() -> None:
    con_recibos = persona(nombre_recibos="Ramos Díaz, Valentina")
    assert revisar(con_recibos).campos == ("nombre_recibos",)
    with pytest.raises(SinPermiso):
        revisar(con_recibos, rol=Rol.ASISTENTE)


@pytest.mark.parametrize("valor", ["Castillo Robles, Edward F.", "Inversiones Ramos & Díaz S.A.C."])
def test_acepta_el_nombre_como_figura_en_los_recibos(valor: str) -> None:
    assert persona(nombre_recibos=f"  {valor} ").nombre_recibos == valor


@pytest.mark.parametrize("valor", ["<b>Valentina</b>", "-Valentina", "x" * 121])
def test_rechaza_un_nombre_en_recibos_invalido(valor: str) -> None:
    with pytest.raises(DatosInvalidos) as error:
        persona(nombre_recibos=valor)
    assert "nombre_recibos" in error.value.campos


def test_valida_el_cargo() -> None:
    assert validar_cargo("  Jefa de  administración ") == "Jefa de administración"
    assert validar_cargo("   ") is None
    with pytest.raises(DatosInvalidos):
        validar_cargo("1")
