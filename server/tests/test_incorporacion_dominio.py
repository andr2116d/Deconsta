import pytest

from app.acceso.dominio.errores import DatosInvalidos, DocumentosDesactualizados
from app.acceso.dominio.incorporacion import (
    DocumentoLegal,
    PasoPendiente,
    Seccion,
    TipoDocumentoLegal,
    documentos_a_aceptar,
    pasos_pendientes,
)
from app.acceso.dominio.modelos import Rol
from tests.test_acceso_dominio import AHORA, usuario

TERMINOS, PRIVACIDAD = TipoDocumentoLegal.TERMINOS, TipoDocumentoLegal.PRIVACIDAD


def documento(tipo: TipoDocumentoLegal, version: int) -> DocumentoLegal:
    return DocumentoLegal(1, tipo, version, "Título", "Resumen", (Seccion("S", ("P",)),), AHORA)


VIGENTES = [documento(TERMINOS, 2), documento(PRIVACIDAD, 1)]


def test_la_contrasena_temporal_va_antes_que_los_documentos() -> None:
    cuenta = usuario(Rol.ASISTENTE)
    assert pasos_pendientes(cuenta, True) == (PasoPendiente.CAMBIAR_CONTRASENA,)
    cuenta.debe_cambiar_contrasena = False
    assert pasos_pendientes(cuenta, True) == (PasoPendiente.ACEPTAR_DOCUMENTOS,)
    assert pasos_pendientes(cuenta, False) == ()


def test_acepta_solo_las_versiones_vigentes_de_todos_los_documentos() -> None:
    assert documentos_a_aceptar(VIGENTES, {TERMINOS: 2, PRIVACIDAD: 1}) == VIGENTES


@pytest.mark.parametrize("aceptados", [{TERMINOS: 2}, {PRIVACIDAD: 1}, {}])
def test_rechaza_una_aceptacion_incompleta(aceptados: dict[TipoDocumentoLegal, int]) -> None:
    with pytest.raises(DatosInvalidos):
        documentos_a_aceptar(VIGENTES, aceptados)


def test_rechaza_aceptar_una_version_que_ya_no_rige() -> None:
    with pytest.raises(DocumentosDesactualizados):
        documentos_a_aceptar(VIGENTES, {TERMINOS: 1, PRIVACIDAD: 1})
