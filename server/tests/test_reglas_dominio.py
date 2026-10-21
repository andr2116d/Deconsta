from decimal import Decimal

import pytest

from app.acceso.dominio.modelos import Rol
from app.reglas.dominio.errores import ReglaInvalida
from app.reglas.dominio.evaluacion import (
    Identidad,
    MotivoAutorizacion,
    TitularDelDocumento,
    evaluar,
)
from app.reglas.dominio.importes import a_importe, error_importe, formatear_soles
from app.reglas.dominio.titulares import (
    DatosTitular,
    Documento,
    TipoDocumentoTitular,
    nombres_coinciden,
    ruc_valido,
)

DNI = TipoDocumentoTitular.DNI
GERENTE = Identidad(("Juan Carlos Pérez Gómez",), Documento(DNI, "45678912"), "Tú")
ESPOSA = Identidad(("María de los Ángeles Ruiz Soto",), None, "Esposa")


@pytest.mark.parametrize(
    ("valor", "mensaje"),
    [
        ("", "Escribe el importe en soles."),
        ("abc", "con hasta dos decimales"),
        ("12.345", "con hasta dos decimales"),
        ("2 900", "con hasta dos decimales"),
        ("0", "mayor que cero"),
        ("0.00", "mayor que cero"),
    ],
)
def test_rechaza_importes_invalidos(valor: str, mensaje: str) -> None:
    assert mensaje in (error_importe(valor) or "")


def test_acepta_importes_en_soles_con_punto_o_coma() -> None:
    assert error_importe("2900,5") is None
    assert a_importe("2900,5") == Decimal("2900.50")
    assert formatear_soles(Decimal("2900.5")) == "S/ 2,900.50"


def test_valida_el_digito_verificador_del_ruc() -> None:
    assert ruc_valido("20131312955")  # SUNAT
    assert not ruc_valido("20131312956")
    assert not ruc_valido("30131312955")


@pytest.mark.parametrize(
    ("en_recibo", "registrado", "coinciden"),
    [
        ("PEREZ GOMEZ JUAN C", "Juan Carlos Pérez Gómez", True),
        ("Juan Pérez", "Juan Carlos Pérez Gómez", True),
        ("RUIZ SOTO MARIA ANGELES", "María de los Ángeles Ruiz Soto", True),
        ("Pedro Pérez", "Juan Carlos Pérez Gómez", False),
        ("PEREZ", "Juan Carlos Pérez Gómez", False),
        ("Juan J Pérez", "Juan Carlos Pérez Gómez", False),
    ],
)
def test_reconoce_el_nombre_sin_importar_orden_tildes_ni_iniciales(
    en_recibo: str, registrado: str, coinciden: bool
) -> None:
    assert nombres_coinciden(en_recibo, registrado) is coinciden


def test_un_ruc_10_contiene_el_dni_de_su_titular() -> None:
    dni = Documento(DNI, "45678912")
    assert dni.coincide(Documento(TipoDocumentoTitular.RUC, "10456789124"))
    assert not dni.coincide(Documento(TipoDocumentoTitular.RUC, "20131312955"))


def test_reune_los_errores_de_un_titular_invalido() -> None:
    with pytest.raises(ReglaInvalida) as error:
        DatosTitular.crear(
            nombre="Rosa", tipo_documento="ruc", numero_documento="20131312956", relacion=None
        )
    assert set(error.value.campos) == {"nombre", "numero_documento"}


def evaluacion(importe: str, nombre: str | None = None, *, registra: Rol = Rol.ASISTENTE, **otros):
    return evaluar(
        registra=registra,
        importe=Decimal(importe),
        limite=otros.get("limite", Decimal("2900")),
        titular=TitularDelDocumento(nombre, otros.get("documento")),
        identidades=[GERENTE, ESPOSA],
    )


def test_pide_autorizacion_solo_por_encima_del_limite() -> None:
    assert evaluacion("2900.00", "PEREZ GOMEZ JUAN").motivos == ()
    sobre = evaluacion("2900.01", "PEREZ GOMEZ JUAN")
    assert [m.codigo for m in sobre.motivos] == [MotivoAutorizacion.IMPORTE_SOBRE_LIMITE]
    assert "S/ 2,900.01 supera tu límite de S/ 2,900.00" in sobre.motivos[0].detalle
    # Sin límite configurado, el importe no detiene nada.
    assert evaluacion("99999", "PEREZ GOMEZ JUAN", limite=None).motivos == ()


def test_reconoce_al_gerente_y_a_sus_titulares_autorizados() -> None:
    assert evaluacion("100", "RUIZ SOTO MARIA").titular_reconocido == "Esposa"
    otro = evaluacion("100", "Pepito Pérez")
    assert [m.codigo for m in otro.motivos] == [MotivoAutorizacion.TITULAR_DISTINTO]
    # Mismo nombre que el gerente pero otro DNI: es otra persona.
    homonimo = evaluacion("100", "Juan Pérez", documento=Documento(DNI, "11111111"))
    assert homonimo.requiere_autorizacion


def test_sin_titular_legible_no_se_marca_como_de_otro_titular() -> None:
    assert evaluacion("150").motivos == ()


def test_lo_que_registra_el_gerente_no_espera_autorizacion() -> None:
    propio = evaluacion("5000", "Pepito Pérez", registra=Rol.GERENTE)
    assert not propio.requiere_autorizacion
    assert [m.codigo for m in propio.avisos] == [MotivoAutorizacion.TITULAR_DISTINTO]
