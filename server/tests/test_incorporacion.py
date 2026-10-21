"""Flujo del primer ingreso: contraseña temporal, documentos legales y entrada al espacio."""

from fastapi.testclient import TestClient

from tests.conftest import Equipo, consultar

LOGIN = "/api/v1/auth/login"
CONTRASENA = "/api/v1/auth/contrasena"
DOCUMENTOS = "/api/v1/documentos-legales"
ACEPTACION = "/api/v1/documentos-legales/aceptacion"
ESPACIO = "/api/v1/espacio"
NUEVA = "Ciruela-Rosa-2026"


def versiones(terminos: int, privacidad: int) -> dict:
    return {
        "documentos": [
            {"tipo": "terminos", "version": terminos},
            {"tipo": "privacidad", "version": privacidad},
        ]
    }


VIGENTES = versiones(1, 1)


def base_de(cliente: TestClient) -> str:
    return cliente.app.state.contenedor.config.database_url  # type: ignore[attr-defined]


def ingresar(cliente: TestClient, usuario: str, contrasena: str) -> dict:
    respuesta = cliente.post(LOGIN, json={"nombre_usuario": usuario, "contrasena": contrasena})
    assert respuesta.status_code == 200, respuesta.json()
    return respuesta.json()


def cambiar(cliente: TestClient, actual: str, nueva: str = NUEVA):
    return cliente.post(CONTRASENA, json={"contrasena_actual": actual, "contrasena_nueva": nueva})


def pendiente(respuesta) -> list[str]:
    assert respuesta.status_code == 403, respuesta.json()
    assert respuesta.json()["code"] == "INCORPORACION_PENDIENTE"
    return respuesta.json()["pending_steps"]


def test_el_primer_ingreso_exige_cada_paso_en_orden(cliente: TestClient, equipo: Equipo) -> None:
    asistente = equipo.asistente
    ingreso = ingresar(cliente, asistente.usuario, asistente.contrasena)
    assert ingreso["pasos_pendientes"] == ["cambiar_contrasena"]
    assert asistente.contrasena not in str(ingreso)

    # Ni el espacio ni la aceptación se alcanzan llamando a la API directamente.
    assert pendiente(cliente.get(ESPACIO)) == ["cambiar_contrasena"]
    assert pendiente(cliente.post(ACEPTACION, json=VIGENTES)) == ["cambiar_contrasena"]

    # Un cambio rechazado no avanza el paso.
    assert cambiar(cliente, asistente.contrasena, "corta1").status_code == 422
    assert cliente.get("/api/v1/auth/me").json()["pasos_pendientes"] == ["cambiar_contrasena"]

    cambio = cambiar(cliente, asistente.contrasena)
    assert cambio.status_code == 200
    assert cambio.json()["pasos_pendientes"] == ["aceptar_documentos"]
    assert pendiente(cliente.get(ESPACIO)) == ["aceptar_documentos"]

    # Leer los documentos no cuenta como aceptarlos.
    documentos = cliente.get(DOCUMENTOS).json()
    assert [(d["tipo"], d["version"], d["aceptado_en"]) for d in documentos] == [
        ("privacidad", 1, None),
        ("terminos", 1, None),
    ]
    assert all(d["secciones"] for d in documentos)
    assert pendiente(cliente.get(ESPACIO)) == ["aceptar_documentos"]

    aceptacion = cliente.post(ACEPTACION, json=VIGENTES)
    assert aceptacion.status_code == 200
    assert aceptacion.json()["pasos_pendientes"] == []
    assert cliente.get(ESPACIO).json() == {
        "usuario": ingreso["usuario"],
        "disponible": False,
    }
    assert all(d["aceptado_en"] for d in cliente.get(DOCUMENTOS).json())


def test_la_aceptacion_queda_registrada_una_sola_vez(cliente: TestClient, equipo: Equipo) -> None:
    gerente = equipo.gerente
    ingresar(cliente, gerente.usuario, gerente.contrasena)
    cambiar(cliente, gerente.contrasena)

    assert cliente.post(ACEPTACION, json=VIGENTES).status_code == 200
    assert cliente.post(ACEPTACION, json=VIGENTES).status_code == 200

    base = base_de(cliente)
    assert consultar(
        base,
        "SELECT d.tipo, d.version FROM aceptacion_documento a"
        " JOIN documento_legal d ON d.id = a.documento_id WHERE a.usuario_id = %s ORDER BY 1",
        gerente.id,
    ) == [("privacidad", 1), ("terminos", 1)]
    eventos = consultar(
        base,
        "SELECT actor_id, jsonb_array_length(detalle->'documentos') FROM auditoria"
        " WHERE accion = 'DOCUMENTOS_ACEPTADOS'",
    )
    assert eventos == [(gerente.id, 2)]

    # El siguiente ingreso ya no pide nada.
    otra = TestClient(cliente.app)
    assert ingresar(otra, gerente.usuario, NUEVA)["pasos_pendientes"] == []
    assert otra.get(ESPACIO).status_code == 200


def test_rechaza_aceptaciones_incompletas_o_desactualizadas(
    cliente: TestClient, equipo: Equipo
) -> None:
    gerente = equipo.gerente
    ingresar(cliente, gerente.usuario, gerente.contrasena)
    cambiar(cliente, gerente.contrasena)

    solo_terminos = cliente.post(
        ACEPTACION, json={"documentos": [{"tipo": "terminos", "version": 1}]}
    )
    assert solo_terminos.status_code == 422
    assert solo_terminos.json()["fields"]["documentos"]
    assert cliente.post(ACEPTACION, json={}).status_code == 422
    desconocido = {"documentos": [{"tipo": "contrato", "version": 1}]}
    assert cliente.post(ACEPTACION, json=desconocido).status_code == 422
    vieja = cliente.post(ACEPTACION, json=versiones(1, 2))
    assert vieja.json()["code"] == "DOCUMENTOS_DESACTUALIZADOS"
    assert consultar(base_de(cliente), "SELECT count(*) FROM aceptacion_documento") == [(0,)]


def test_una_version_nueva_vuelve_a_pedir_la_aceptacion(
    cliente: TestClient, equipo: Equipo
) -> None:
    gerente = equipo.gerente
    ingresar(cliente, gerente.usuario, gerente.contrasena)
    cambiar(cliente, gerente.contrasena)
    cliente.post(ACEPTACION, json=VIGENTES)
    base = base_de(cliente)

    publicar = (
        "INSERT INTO documento_legal (tipo, version, titulo, resumen, secciones, vigente_desde)"
        " VALUES ('terminos', %s, 'Términos', 'Resumen',"
        ' \'[{"titulo": "T", "parrafos": ["P"]}]\', now() + %s::interval)'
    )
    # Una versión con vigencia futura todavía no se exige.
    consultar(base, publicar, 3, "30 days")
    assert cliente.get(ESPACIO).status_code == 200

    consultar(base, publicar, 2, "0 seconds")
    # La sesión ya abierta también queda retenida hasta aceptar la versión 2.
    assert cliente.get("/api/v1/auth/me").json()["pasos_pendientes"] == ["aceptar_documentos"]
    assert pendiente(cliente.get(ESPACIO)) == ["aceptar_documentos"]
    assert cliente.post(ACEPTACION, json=VIGENTES).json()["code"] == "DOCUMENTOS_DESACTUALIZADOS"

    assert cliente.post(ACEPTACION, json=versiones(2, 1)).json()["pasos_pendientes"] == []
    assert cliente.get(ESPACIO).status_code == 200


def test_los_documentos_exigen_sesion(cliente: TestClient) -> None:
    assert cliente.get(DOCUMENTOS).status_code == 401
    assert cliente.post(ACEPTACION, json=VIGENTES).status_code == 401
    assert cliente.get(ESPACIO).status_code == 401
