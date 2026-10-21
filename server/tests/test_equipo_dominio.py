from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.acceso.dominio.datos_personales import DatosPersonales
from app.acceso.dominio.errores import DatosInvalidos
from app.acceso.dominio.incorporacion import PasoPendiente, pasos_pendientes
from app.acceso.dominio.modelos import CausaBloqueo, Rol, Usuario

AHORA = datetime(2026, 10, 21, tzinfo=UTC)


def persona(**cambios: object) -> DatosPersonales:
    valores: dict[str, object] = {
        "nombres": "Lucía",
        "apellidos": "Vega",
        "correo": None,
        "tipo_documento": "dni",
        "numero_documento": "41234567",
        "telefono": "987654321",
        "correo_obligatorio": False,
        "telefono_obligatorio": True,
    }
    valores.update(cambios)
    return DatosPersonales.crear(**valores)  # type: ignore[arg-type]


@pytest.mark.parametrize("valor", ["987654321", "+51 987 654 321", "51987654321", "987-654-321"])
def test_acepta_un_celular_peruano_y_lo_guarda_con_9_digitos(valor: str) -> None:
    assert persona(telefono=valor).telefono == "987654321"


@pytest.mark.parametrize("valor", ["812345678", "98765432", "9876543210", "+1 987654321"])
def test_rechaza_lo_que_no_es_un_celular_peruano(valor: str) -> None:
    with pytest.raises(DatosInvalidos) as error:
        persona(telefono=valor)
    assert "celular peruano" in error.value.campos["telefono"]


def test_el_celular_es_obligatorio_al_registrar_una_asistente() -> None:
    with pytest.raises(DatosInvalidos) as error:
        persona(telefono="")
    assert error.value.campos["telefono"] == "Ingresa el número de celular."


@pytest.mark.parametrize(
    ("valor", "pista"),
    [("lucia.ejemplo.pe", "Incluye la @"), ("lucia@ejemplo", "dominio con extensión")],
)
def test_explica_que_le_falta_al_correo(valor: str, pista: str) -> None:
    with pytest.raises(DatosInvalidos) as error:
        persona(correo=valor)
    assert pista in error.value.campos["correo"]


def test_el_correo_puede_faltar_solo_si_no_es_obligatorio() -> None:
    assert persona().correo is None
    with pytest.raises(DatosInvalidos) as error:
        persona(correo_obligatorio=True)
    assert "correo" in error.value.campos


def test_la_asistente_confirma_sus_datos_despues_de_aceptar_los_documentos() -> None:
    assert pasos_pendientes(True, True) == (
        PasoPendiente.ACEPTAR_DOCUMENTOS,
        PasoPendiente.COMPLETAR_DATOS,
    )
    assert pasos_pendientes(False, True) == (PasoPendiente.COMPLETAR_DATOS,)


def test_recuperar_deja_a_la_asistente_como_recien_registrada() -> None:
    asistente = Usuario(
        id=uuid4(),
        rol=Rol.ASISTENTE,
        gerente_id=uuid4(),
        nombre_usuario="lucia.vega",
        nombres="Lucía",
        contrasena_hash="anterior",
        debe_cambiar_contrasena=False,
        contrasena_actualizada_en=AHORA,
        ultimo_ingreso_en=AHORA,
        intentos_fallidos=5,
        bloqueada_en=AHORA,
        causa_bloqueo=CausaBloqueo.INTENTOS_FALLIDOS,
        eliminada_en=AHORA,
        datos_confirmados_en=AHORA,
    )

    asistente.recuperar("nuevo", AHORA)

    assert not asistente.eliminada and not asistente.bloqueada
    assert asistente.causa_bloqueo is None and asistente.intentos_fallidos == 0
    assert asistente.debe_cambiar_contrasena and asistente.debe_confirmar_datos
    assert asistente.contrasena_hash == "nuevo"
