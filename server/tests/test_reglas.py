import pytest
from fastapi.testclient import TestClient

from tests.conftest import Equipo, FabricaCliente, consultar
from tests.test_categorias import sesion
from tests.test_contrasena_y_desbloqueo import base_de

REGLAS = "/api/v1/reglas"
TITULARES = f"{REGLAS}/titulares"
ESPOSA = {
    "nombre": "María de los Ángeles Ruiz Soto",
    "tipo_documento": "dni",
    "numero_documento": "41234568",
    "relacion": "Esposa",
    "autorizacion_declarada": True,
}


@pytest.fixture
def gerente(cliente: TestClient, equipo: Equipo) -> TestClient:
    return sesion(cliente, equipo.gerente)


def agregar(cliente: TestClient, **cambios: object) -> dict:
    respuesta = cliente.post(TITULARES, json={**ESPOSA, **cambios})
    assert respuesta.status_code == 201, respuesta.json()
    return respuesta.json()


def evaluar(cliente: TestClient, importe: str, nombre: str | None = None) -> dict:
    respuesta = cliente.post(
        f"{REGLAS}/evaluacion", json={"importe": importe, "titular_nombre": nombre}
    )
    assert respuesta.status_code == 200, respuesta.json()
    return respuesta.json()


def test_el_gerente_fija_cambia_y_quita_su_limite(gerente: TestClient) -> None:
    assert gerente.get(REGLAS).json()["limite_importe"] is None

    fijado = gerente.post(f"{REGLAS}/limite", json={"limite_importe": "2900,5"})
    assert fijado.status_code == 200
    assert fijado.json()["limite_importe"] == "2900.50"
    repetido = gerente.post(f"{REGLAS}/limite", json={"limite_importe": "2900.50"})
    assert repetido.json()["code"] == "SIN_CAMBIOS"
    quitado = gerente.post(f"{REGLAS}/limite", json={"limite_importe": None})
    assert quitado.json()["limite_importe"] is None

    auditoria = consultar(
        base_de(gerente),
        "SELECT detalle FROM auditoria WHERE accion = 'LIMITE_AUTORIZACION_CAMBIADO' ORDER BY id",
    )
    assert [fila[0] for fila in auditoria] == [
        {"antes": None, "despues": "2900.50"},
        {"antes": "2900.50", "despues": None},
    ]


@pytest.mark.parametrize(
    ("cuerpo", "codigo"),
    [
        ({}, "CAMPOS_OBLIGATORIOS"),
        ({"limite_importe": "  "}, "CAMPOS_OBLIGATORIOS"),
        ({"limite_importe": "0"}, "DATOS_INVALIDOS"),
        ({"limite_importe": "10000000"}, "DATOS_INVALIDOS"),
        ({"limite_importe": "1.234"}, "DATOS_INVALIDOS"),
    ],
)
def test_rechaza_un_limite_vacio_o_invalido(gerente: TestClient, cuerpo: dict, codigo: str) -> None:
    respuesta = gerente.post(f"{REGLAS}/limite", json=cuerpo)

    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == codigo
    assert "limite_importe" in respuesta.json()["fields"]


def test_agrega_un_titular_cifrado_y_sin_datos_personales_en_la_auditoria(
    gerente: TestClient,
) -> None:
    creado = agregar(gerente)

    assert creado["documento"] == "•••• 4568"
    assert creado["relacion"] == "Esposa"
    url = base_de(gerente)
    guardado = consultar(
        url, "SELECT nombre_cifrado, numero_documento_cifrado FROM titular_autorizado"
    )
    assert b"Ruiz" not in bytes(guardado[0][0])
    assert b"41234568" not in bytes(guardado[0][1])
    auditoria = consultar(
        url, "SELECT detalle::text FROM auditoria WHERE accion = 'TITULAR_AUTORIZADO_AGREGADO'"
    )
    assert "Ruiz" not in auditoria[0][0] and "41234568" not in auditoria[0][0]


def test_rechaza_el_formulario_del_titular_con_el_nombre_vacio(gerente: TestClient) -> None:
    respuesta = gerente.post(TITULARES, json={"autorizacion_declarada": True})

    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "CAMPOS_OBLIGATORIOS"
    assert respuesta.json()["fields"] == {
        "nombre": "Escribe el nombre como aparece en sus recibos."
    }


@pytest.mark.parametrize(
    ("cambios", "codigo", "campo"),
    [
        ({"autorizacion_declarada": False}, "AUTORIZACION_NO_DECLARADA", "autorizacion_declarada"),
        ({"numero_documento": "45678912"}, "TITULAR_ES_GERENTE", "numero_documento"),
        (
            {"tipo_documento": "ruc", "numero_documento": "20131312956"},
            "DATOS_INVALIDOS",
            "numero_documento",
        ),
        ({"numero_documento": None}, "DATOS_INVALIDOS", "numero_documento"),
    ],
)
def test_valida_la_autorizacion_y_el_documento_del_titular(
    gerente: TestClient, cambios: dict, codigo: str, campo: str
) -> None:
    respuesta = gerente.post(TITULARES, json={**ESPOSA, **cambios})

    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == codigo
    assert campo in respuesta.json()["fields"]


def test_no_repite_titulares_por_nombre_ni_por_documento(gerente: TestClient) -> None:
    agregar(gerente)

    por_nombre = gerente.post(
        TITULARES,
        json={
            **ESPOSA,
            "nombre": "RUIZ SOTO MARIA ANGELES",
            "numero_documento": None,
            "tipo_documento": None,
        },
    )
    por_documento = gerente.post(TITULARES, json={**ESPOSA, "nombre": "Otra Persona"})

    assert por_nombre.status_code == por_documento.status_code == 409
    assert "nombre" in por_nombre.json()["fields"]
    assert "numero_documento" in por_documento.json()["fields"]


def test_edita_y_quita_titulares_conservando_el_historial(gerente: TestClient) -> None:
    titular = agregar(gerente)
    ruta = f"{TITULARES}/{titular['id']}"

    editado = gerente.post(
        f"{ruta}/edicion", json={"nombre": ESPOSA["nombre"], "relacion": "Pareja"}
    )
    assert editado.json()["relacion"] == "Pareja"
    sin_cambios = gerente.post(
        f"{ruta}/edicion", json={"nombre": ESPOSA["nombre"], "relacion": "Pareja"}
    )
    assert sin_cambios.json()["code"] == "SIN_CAMBIOS"

    assert gerente.post(f"{ruta}/eliminacion", json={"motivo": "Ya no"}).status_code == 204
    assert gerente.get(REGLAS).json()["titulares"] == []
    assert gerente.post(f"{ruta}/edicion", json={"nombre": "Otra Persona"}).status_code == 404
    # Quitado no es borrado: la fila y la auditoría siguen, y se puede volver a agregar.
    assert consultar(base_de(gerente), "SELECT count(*) FROM titular_autorizado") == [(1,)]
    agregar(gerente)


def test_las_reglas_definen_que_espera_autorizacion(gerente: TestClient) -> None:
    gerente.post(f"{REGLAS}/limite", json={"limite_importe": "2900"})
    titular = agregar(gerente)

    sobre_limite = evaluar(gerente, "3000", "Pepito Pérez")
    assert sobre_limite["requiere_autorizacion"] is True
    assert [m["codigo"] for m in sobre_limite["motivos"]] == [
        "IMPORTE_SOBRE_LIMITE",
        "TITULAR_DISTINTO",
    ]
    assert evaluar(gerente, "500", "RUIZ SOTO MARIA")["titular_reconocido"] == "Esposa"
    # El propio gerente (Valentina Ramos) siempre se reconoce.
    assert evaluar(gerente, "500", "RAMOS VALENTINA")["titular_reconocido"] == "Tú"

    gerente.post(f"{TITULARES}/{titular['id']}/eliminacion")
    assert evaluar(gerente, "500", "RUIZ SOTO MARIA")["requiere_autorizacion"] is True


def test_solo_el_gerente_ve_y_cambia_sus_reglas(
    cliente: TestClient, gerente: TestClient, equipo: Equipo
) -> None:
    titular = agregar(gerente)

    asistente = sesion(cliente, equipo.asistente)
    assert asistente.get(REGLAS).status_code == 403
    assert asistente.post(f"{REGLAS}/limite", json={"limite_importe": "1"}).status_code == 403
    assert asistente.post(TITULARES, json=ESPOSA).json()["code"] == "SIN_PERMISO"

    otro = sesion(cliente, equipo.otro_gerente)
    assert otro.get(REGLAS).json()["titulares"] == []
    ajeno = otro.post(f"{TITULARES}/{titular['id']}/eliminacion")
    assert ajeno.status_code == 404
    assert ajeno.json()["code"] == "TITULAR_NO_ENCONTRADO"
    assert TestClient(cliente.app).get(REGLAS).status_code == 401


def test_limita_los_titulares_vigentes(
    gerente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.reglas.aplicacion.reglas.MAXIMO_TITULARES", 1)
    agregar(gerente)

    respuesta = gerente.post(
        TITULARES,
        json={
            **ESPOSA,
            "nombre": "Inversiones Ramos S.A.C.",
            "tipo_documento": "ruc",
            "numero_documento": "20131312955",
        },
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["code"] == "LIMITE_TITULARES"


def test_limita_los_intentos_de_cada_gerente(crear_cliente: FabricaCliente, equipo: Equipo) -> None:
    gerente = sesion(crear_cliente(limite_gestion_reglas=2), equipo.gerente)
    gerente.post(f"{REGLAS}/limite", json={"limite_importe": "100"})
    gerente.post(f"{REGLAS}/limite", json={"limite_importe": "200"})

    respuesta = gerente.post(f"{REGLAS}/limite", json={"limite_importe": "300"})

    assert respuesta.status_code == 429
    assert respuesta.json()["code"] == "DEMASIADAS_SOLICITUDES"
