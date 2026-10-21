from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.acceso.dominio.modelos import Rol
from app.documentos.dominio.analisis import (
    Metadatos,
    clave_negocio,
    contrastar,
    estado_tras_analisis,
    evaluar_metadatos,
    mismos_numeros,
    senal_legibilidad,
)
from app.documentos.dominio.archivos import detectar_tipo, limpiar_nombre, validar_archivo
from app.documentos.dominio.errores import ArchivoDemasiadoGrande, ArchivoInvalido, ArchivoVacio
from app.documentos.dominio.modelos import (
    TAMANO_MAXIMO,
    Analisis,
    Capa,
    DatosLeidos,
    EstadoDocumento,
    Lectura,
    Riesgo,
    Senal,
    TipoArchivo,
    TipoDocumento,
)
from tests.dobles import TEXTO_RECIBO, imagen, pdf

RECIBO = DatosLeidos(
    tipo=TipoDocumento.RECIBO_SERVICIO,
    emisor="Hidrandina S.A.",
    emisor_ruc="20132023540",
    codigo_pago="54871236",
    numero_documento="S001-00451236",
    periodo="2026-09",
    importe=Decimal("182.40"),
)


def test_el_tipo_sale_del_contenido_y_no_de_la_extension() -> None:
    assert detectar_tipo(pdf()) is TipoArchivo.PDF
    assert detectar_tipo(imagen()) is TipoArchivo.PNG
    assert detectar_tipo(imagen(formato="JPEG")) is TipoArchivo.JPEG
    # Un ejecutable renombrado a «recibo.pdf» no pasa.
    with pytest.raises(ArchivoInvalido):
        validar_archivo(b"MZ\x90\x00" + b"\x00" * 100)
    with pytest.raises(ArchivoVacio):
        validar_archivo(b"")
    with pytest.raises(ArchivoDemasiadoGrande):
        validar_archivo(b"%PDF-" + b"0" * TAMANO_MAXIMO)


def test_el_nombre_del_archivo_se_guarda_sin_rutas_ni_invisibles() -> None:
    assert limpiar_nombre("C:\\fakepath\\recibo\u202eluz.pdf", TipoArchivo.PDF) == "reciboluz.pdf"
    assert limpiar_nombre("   ", TipoArchivo.JPEG) == "documento.jpg"


@pytest.mark.parametrize(
    ("metadatos", "codigo", "riesgo"),
    [
        (Metadatos(programas=("Adobe Photoshop 26.1",)), "EDITOR_DE_IMAGENES", Riesgo.ALTO),
        (Metadatos(programas=("Canva",)), "EDITOR_DE_IMAGENES", Riesgo.ALTO),
        (Metadatos(programas=("iLovePDF",)), "EDITADO_DESPUES", Riesgo.MEDIO),
        (
            Metadatos(programas=("Microsoft Word para Microsoft 365",)),
            "CREADO_EN_PROCESADOR",
            Riesgo.MEDIO,
        ),
        (Metadatos(revisiones=3), "PDF_MODIFICADO", Riesgo.MEDIO),
        (Metadatos(con_javascript=True), "CONTENIDO_ACTIVO", Riesgo.MEDIO),
    ],
)
def test_los_metadatos_delatan_la_edicion(
    metadatos: Metadatos, codigo: str, riesgo: Riesgo
) -> None:
    senales = evaluar_metadatos(metadatos)
    assert [(s.codigo, s.riesgo) for s in senales] == [(codigo, riesgo)]


def test_un_pdf_de_un_sistema_emisor_o_firmado_no_levanta_sospechas() -> None:
    assert evaluar_metadatos(Metadatos(programas=("JasperReports Library 6.20", "iText 7"))) == []
    # La firma digital agrega su propia revisión al PDF.
    assert evaluar_metadatos(Metadatos(revisiones=2, firmado=True)) == []
    # «Pages» cuenta como procesador solo como palabra completa.
    assert evaluar_metadatos(Metadatos(programas=("WebPages Builder",))) == []


def test_un_documento_sin_texto_legible_es_ilegible() -> None:
    assert senal_legibilidad(Lectura(TEXTO_RECIBO, 0.95, 1)) is None
    assert senal_legibilidad(Lectura("", 0.0, 1)) is not None
    assert senal_legibilidad(Lectura(TEXTO_RECIBO, 0.4, 1)) is not None


def test_lo_que_propone_la_ia_debe_estar_escrito_en_el_documento() -> None:
    assert contrastar(RECIBO, Lectura(TEXTO_RECIBO, 0.9, 1)) == []
    # Con separador de miles también se reconoce el importe.
    miles = Lectura(TEXTO_RECIBO.replace("182.40", "1,182.40"), 0.9, 1)
    assert contrastar(DatosLeidos(importe=Decimal("1182.40")), miles) == []

    inventado = DatosLeidos(importe=Decimal("82.40"), codigo_pago="99999999")
    codigos = [s.codigo for s in contrastar(inventado, Lectura(TEXTO_RECIBO, 0.9, 1))]
    assert codigos == ["IMPORTE_NO_CONFIRMADO", "CODIGO_NO_CONFIRMADO"]


def test_la_clave_de_negocio_reconoce_el_mismo_recibo_escrito_distinto() -> None:
    otra_lectura = DatosLeidos(
        tipo=TipoDocumento.RECIBO_SERVICIO,
        emisor="HIDRANDINA SA",
        emisor_ruc="20132023540",
        codigo_pago="5487 1236",
        periodo="2026-09",
    )
    assert clave_negocio(RECIBO) == clave_negocio(otra_lectura)
    # El recibo del mes siguiente es otro documento.
    octubre = DatosLeidos(**{**RECIBO.__dict__, "periodo": "2026-10"})
    assert clave_negocio(octubre) != clave_negocio(RECIBO)
    # Sin número no hay clave: no se puede decir que dos boletas son la misma.
    assert clave_negocio(DatosLeidos(tipo=TipoDocumento.BOLETA, emisor_ruc="20100070970")) is None


def test_dos_documentos_con_casi_los_mismos_numeros_son_el_mismo() -> None:
    propios = {bytes([i]) for i in range(10)}
    assert mismos_numeros(propios, propios | {b"x"})
    assert not mismos_numeros(propios, {bytes([i]) for i in range(5, 15)})
    assert not mismos_numeros({b"a", b"b"}, {b"a", b"b"})


def test_con_riesgo_alto_se_rechaza_lo_de_la_asistente_y_al_gerente_solo_se_le_advierte() -> None:
    alterado = Analisis(
        RECIBO, (Senal(Capa.METADATOS, "EDITOR_DE_IMAGENES", "Photoshop", Riesgo.ALTO),)
    )
    assert estado_tras_analisis(alterado, Rol.ASISTENTE) is EstadoDocumento.RECHAZADO
    assert estado_tras_analisis(alterado, Rol.GERENTE) is EstadoDocumento.LISTO
    assert estado_tras_analisis(Analisis(RECIBO), Rol.ASISTENTE) is EstadoDocumento.LISTO


def test_la_fecha_de_modificacion_posterior_es_solo_informativa() -> None:
    senales = evaluar_metadatos(
        Metadatos(
            creado_en=datetime(2026, 10, 1, tzinfo=UTC),
            modificado_en=datetime(2026, 10, 5, tzinfo=UTC),
        )
    )
    assert [(s.codigo, s.riesgo) for s in senales] == [
        ("FECHA_MODIFICACION_POSTERIOR", Riesgo.BAJO)
    ]
