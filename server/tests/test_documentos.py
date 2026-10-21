from dataclasses import replace
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.documentos.dominio.modelos import DatosLeidos, TipoDocumento
from tests.conftest import Equipo, consultar
from tests.dobles import Dobles, imagen, pdf
from tests.test_categorias import sesion
from tests.test_contrasena_y_desbloqueo import base_de

DOCUMENTOS = "/api/v1/documentos"
LEIDO = DatosLeidos(
    tipo=TipoDocumento.RECIBO_SERVICIO,
    emisor="Hidrandina S.A.",
    emisor_ruc="20132023540",
    concepto="Luz Hidrandina setiembre 2026",
    titular_nombre="RAMOS DIAZ VALENTINA",
    codigo_pago="54871236",
    numero_documento="S001-00451236",
    periodo="2026-09",
    importe=Decimal("182.40"),
)


def dobles(cliente: TestClient) -> Dobles:
    return cliente.app.state.dobles  # type: ignore[attr-defined,no-any-return]


@pytest.fixture
def gerente(cliente: TestClient, equipo: Equipo) -> TestClient:
    dobles(cliente).revisor.datos = LEIDO
    return sesion(cliente, equipo.gerente)


@pytest.fixture
def asistente(cliente: TestClient, equipo: Equipo) -> TestClient:
    dobles(cliente).revisor.datos = LEIDO
    return sesion(cliente, equipo.asistente)


def subir(cliente: TestClient, contenido: bytes, nombre: str = "recibo.png") -> dict:
    respuesta = cliente.post(DOCUMENTOS, files={"archivo": (nombre, contenido, "image/png")})
    assert respuesta.status_code == 202, respuesta.json()
    return cliente.get(f"{DOCUMENTOS}/{respuesta.json()['id']}").json()


def test_sin_archivo_responde_que_falta_el_documento(asistente: TestClient) -> None:
    respuesta = asistente.post(DOCUMENTOS)
    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "CAMPOS_OBLIGATORIOS"
    assert set(respuesta.json()["fields"]) == {"archivo"}


@pytest.mark.parametrize(
    ("contenido", "codigo", "estado"),
    [
        (b"MZ\x90\x00 esto es un ejecutable", "ARCHIVO_INVALIDO", 422),
        (b"", "ARCHIVO_VACIO", 422),
        (imagen()[:200], "ARCHIVO_INVALIDO", 422),
        (pdf(paginas=11), "DEMASIADAS_PAGINAS", 422),
        (b"%PDF-" + b"0" * (10 * 1024 * 1024), "ARCHIVO_DEMASIADO_GRANDE", 413),
    ],
)
def test_rechaza_los_archivos_que_no_son_un_documento(
    asistente: TestClient, contenido: bytes, codigo: str, estado: int
) -> None:
    respuesta = asistente.post(DOCUMENTOS, files={"archivo": ("recibo.pdf", contenido)})
    assert respuesta.status_code == estado
    assert respuesta.json()["code"] == codigo


def test_analiza_el_documento_y_lo_guarda_cifrado(
    cliente: TestClient, asistente: TestClient
) -> None:
    contenido = imagen(1)
    documento = subir(asistente, contenido)

    assert documento["estado"] == "listo"
    assert documento["riesgo"] == "bajo"
    assert documento["propuesta"]["importe"] == "182.40"
    assert documento["propuesta"]["codigo_pago"] == "54871236"
    # En el almacenamiento solo hay el archivo cifrado; la API lo entrega descifrado.
    guardado = next(iter(dobles(cliente).almacen.objetos.values()))
    assert contenido not in guardado
    archivo = asistente.get(f"{DOCUMENTOS}/{documento['id']}/contenido")
    assert archivo.content == contenido
    assert archivo.headers["content-type"] == "image/png"
    assert "sandbox" in archivo.headers["content-security-policy"]
    # Lo leído del documento son datos personales: en la base está cifrado.
    filas = consultar(
        base_de(cliente),
        "SELECT analisis_cifrado FROM documento_deuda WHERE id = %s",
        documento["id"],
    )
    assert b"RAMOS" not in bytes(filas[0][0])


def test_un_documento_solo_lo_ven_quien_lo_subio_y_su_gerente(
    cliente: TestClient, asistente: TestClient, gerente: TestClient, equipo: Equipo
) -> None:
    del_gerente = subir(gerente, imagen(2))
    de_la_asistente = subir(asistente, imagen(3))
    otro = sesion(cliente, equipo.otro_gerente)

    assert gerente.get(f"{DOCUMENTOS}/{de_la_asistente['id']}").status_code == 200
    for cuenta, documento in ((asistente, del_gerente), (otro, de_la_asistente)):
        respuesta = cuenta.get(f"{DOCUMENTOS}/{documento['id']}/contenido")
        assert respuesta.status_code == 404
        assert respuesta.json()["code"] == "DOCUMENTO_NO_ENCONTRADO"


def test_un_documento_ilegible_no_llega_a_la_ia(cliente: TestClient, asistente: TestClient) -> None:
    dobles(cliente).lector.texto = "~~ ::"
    documento = subir(asistente, imagen(4))

    assert documento["estado"] == "ilegible"
    assert documento["propuesta"] is None
    assert [s["codigo"] for s in documento["senales"]] == ["DOCUMENTO_ILEGIBLE"]
    assert dobles(cliente).revisor.revisiones == 0


def test_si_la_ia_no_responde_el_documento_queda_dudoso_y_sin_propuesta(
    cliente: TestClient, asistente: TestClient
) -> None:
    dobles(cliente).revisor.falla = True
    documento = subir(asistente, imagen(5))

    assert documento["estado"] == "listo"
    assert documento["riesgo"] == "medio"
    assert documento["propuesta"] is None
    assert [s["codigo"] for s in documento["senales"]] == ["REVISION_INCOMPLETA"]


def test_una_alteracion_clara_rechaza_lo_de_la_asistente_y_al_gerente_lo_advierte(
    cliente: TestClient, asistente: TestClient, gerente: TestClient
) -> None:
    revisor = dobles(cliente).revisor
    revisor.veredicto = "alterado"
    revisor.motivos = ("El total está superpuesto sobre otra cifra",)

    rechazado = subir(asistente, imagen(6))
    assert rechazado["estado"] == "rechazado"
    assert rechazado["senales"][0]["detalle"] == "El total está superpuesto sobre otra cifra."
    assert subir(gerente, imagen(7))["estado"] == "listo"


def test_la_ia_recibe_las_categorias_del_espacio(
    cliente: TestClient, asistente: TestClient, gerente: TestClient
) -> None:
    gerente.post("/api/v1/categorias", json={"nombre": "Luz", "descripcion": "Recibos de luz"})
    subir(asistente, imagen(8))
    assert [c.nombre for c in dobles(cliente).revisor.categorias] == ["Luz"]


def test_un_pdf_editado_despues_queda_dudoso(cliente: TestClient, asistente: TestClient) -> None:
    respuesta = asistente.post(DOCUMENTOS, files={"archivo": ("recibo.pdf", pdf("iLovePDF"))})
    documento = asistente.get(f"{DOCUMENTOS}/{respuesta.json()['id']}").json()
    assert documento["riesgo"] == "medio"
    assert "EDITADO_DESPUES" in [s["codigo"] for s in documento["senales"]]


def test_la_clave_de_negocio_reconoce_el_mismo_recibo_en_otro_archivo(
    cliente: TestClient, asistente: TestClient
) -> None:
    from tests.test_deudas import registrar

    primero = subir(asistente, imagen(9))
    registrada = registrar(asistente, primero["id"]).json()["deuda"]
    # Otra foto del mismo recibo: otro archivo, mismo emisor, suministro y periodo.
    dobles(cliente).revisor.datos = replace(LEIDO, codigo_pago="5487 1236")
    segundo = subir(asistente, imagen(10))

    assert segundo["estado"] == "repetido"
    assert segundo["repetido_de"]["id"] == registrada["id"]
