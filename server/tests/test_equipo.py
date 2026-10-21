import pytest
from fastapi.testclient import TestClient

from tests.conftest import Equipo, FabricaCliente, consultar, habilitar
from tests.test_contrasena_y_desbloqueo import base_de, ingresar

ASISTENTES = "/api/v1/asistentes"
LOGIN = "/api/v1/auth/login"
CONFIRMACION = "/api/v1/cuenta/confirmacion-datos"

DANIELA = {
    "nombres": "Daniela",
    "apellidos": "Torres Ríos",
    "telefono": "+51 912 345 678",
    "tipo_documento": "dni",
    "numero_documento": "44556677",
}


@pytest.fixture
def gerente(cliente: TestClient, equipo: Equipo) -> TestClient:
    """El cliente queda con la sesión del gerente, ya habilitado."""
    habilitar(base_de(cliente), equipo.gerente.id)
    ingresar(cliente, equipo.gerente.usuario, equipo.gerente.contrasena)
    return cliente


def registrar(cliente: TestClient, **cambios: object) -> dict:
    respuesta = cliente.post(ASISTENTES, json={**DANIELA, **cambios})
    assert respuesta.status_code == 201, respuesta.json()
    return respuesta.json()


def test_registra_una_asistente_con_credenciales_generadas(gerente: TestClient) -> None:
    creada = registrar(gerente, cargo="Asistente administrativa")

    assert creada["nombre_usuario"] == "daniela.torres"
    asistente = creada["asistente"]
    assert asistente["telefono"] == "912345678"
    assert asistente["documento"] == "•••• 6677"
    assert asistente["estado"] == "pendiente"
    assert asistente["correo"] is None
    # Ingresa con lo que se le entregó y su bienvenida pide aceptar y confirmar sus datos.
    sesion = ingresar(TestClient(gerente.app), "daniela.torres", creada["contrasena_temporal"])
    assert sesion["debe_cambiar_contrasena"] is True
    assert sesion["pasos_pendientes"] == ["aceptar_documentos", "completar_datos"]
    auditoria = consultar(
        base_de(gerente),
        "SELECT actor_id IS NOT NULL, detalle FROM auditoria"
        " WHERE accion = 'CUENTA_CREADA' AND detalle->>'origen' = 'mi_equipo'",
    )
    assert auditoria[0][0] is True
    assert auditoria[0][1]["usuario_generado"] is True
    assert "contrasena_temporal" not in str(auditoria)


def test_rechaza_el_formulario_con_campos_obligatorios_vacios(gerente: TestClient) -> None:
    respuesta = gerente.post(ASISTENTES, json={"tipo_documento": "dni"})

    assert respuesta.status_code == 422
    assert set(respuesta.json()["fields"]) >= {
        "nombres",
        "apellidos",
        "telefono",
        "numero_documento",
    }


@pytest.mark.parametrize(
    ("cambio", "campo"),
    [
        ({"telefono": "812345678"}, "telefono"),
        ({"numero_documento": "4455667"}, "numero_documento"),
        ({"tipo_documento": "ce", "numero_documento": "12-34"}, "numero_documento"),
        ({"nombres": "Dani3la"}, "nombres"),
    ],
)
def test_valida_celular_documento_y_nombres(gerente: TestClient, cambio: dict, campo: str) -> None:
    respuesta = gerente.post(ASISTENTES, json={**DANIELA, **cambio})
    assert respuesta.status_code == 422
    assert campo in respuesta.json()["fields"]


def test_valida_el_usuario_y_la_contrasena_que_elige_el_gerente(
    gerente: TestClient, equipo: Equipo
) -> None:
    ocupado = gerente.post(ASISTENTES, json={**DANIELA, "nombre_usuario": equipo.gerente.usuario})
    debil = gerente.post(ASISTENTES, json={**DANIELA, "contrasena": "corta1"})
    elegidas = registrar(gerente, nombre_usuario="Dani.Torres", contrasena="Ciruela-Rosa-2026")

    assert ocupado.json()["fields"]["nombre_usuario"] == "Ese usuario ya está en uso."
    assert debil.json()["code"] == "CONTRASENA_INSEGURA"
    assert "contrasena" in debil.json()["fields"]
    assert elegidas["nombre_usuario"] == "dani.torres"
    assert elegidas["contrasena_temporal"] == "Ciruela-Rosa-2026"


def test_no_registra_dos_veces_a_la_misma_persona(gerente: TestClient, equipo: Equipo) -> None:
    creada = registrar(gerente)
    gerente.post(f"{ASISTENTES}/{creada['asistente']['id']}/bloqueo", json={"motivo": "Prueba"})

    repetida = gerente.post(ASISTENTES, json=DANIELA)
    # El documento de otra cuenta (aquí, otro gerente) no revela a quién pertenece.
    ajena = gerente.post(ASISTENTES, json={**DANIELA, "numero_documento": "40000001"})

    assert repetida.status_code == 409
    assert repetida.json()["code"] == "PERSONA_YA_EN_EQUIPO"
    assert "bloqueada" in repetida.json()["detail"]
    assert ajena.status_code == 409
    assert ajena.json()["code"] == "DATOS_DUPLICADOS"


def test_bloquear_cierra_sus_sesiones_y_explica_quien_la_bloqueo(
    gerente: TestClient,
) -> None:
    creada = registrar(gerente)
    asistente = TestClient(gerente.app)
    ingresar(asistente, "daniela.torres", creada["contrasena_temporal"])
    url = f"{ASISTENTES}/{creada['asistente']['id']}"

    bloqueo = gerente.post(f"{url}/bloqueo", json={"motivo": "Vacaciones"})

    assert bloqueo.json()["estado"] == "bloqueada"
    assert bloqueo.json()["causa_bloqueo"] == "gerente"
    assert asistente.get("/api/v1/auth/me").status_code == 401
    rechazo = asistente.post(
        LOGIN,
        json={"nombre_usuario": "daniela.torres", "contrasena": creada["contrasena_temporal"]},
    )
    assert rechazo.status_code == 423
    assert "Tu gerente bloqueó tu cuenta" in rechazo.json()["detail"]
    assert gerente.post(f"{url}/bloqueo").json()["code"] == "CUENTA_YA_BLOQUEADA"

    assert gerente.post(f"{url}/desbloqueo").json()["estado"] == "pendiente"
    ingresar(asistente, "daniela.torres", creada["contrasena_temporal"])


def test_eliminar_impide_ingresar_y_ofrece_recuperarla(gerente: TestClient) -> None:
    creada = registrar(gerente)
    asistente_id = creada["asistente"]["id"]

    assert gerente.post(f"{ASISTENTES}/{asistente_id}/eliminacion").status_code == 204

    assert asistente_id not in [a["id"] for a in gerente.get(ASISTENTES).json()]
    # Una cuenta eliminada responde igual que una inexistente.
    rechazo = gerente.post(
        LOGIN,
        json={"nombre_usuario": "daniela.torres", "contrasena": creada["contrasena_temporal"]},
    )
    assert rechazo.json()["code"] == "CREDENCIALES_INCORRECTAS"
    otra_vez = gerente.post(ASISTENTES, json=DANIELA)
    assert otra_vez.json()["code"] == "ASISTENTE_ELIMINADA"
    assert otra_vez.json()["deleted_account"] == {
        "id": asistente_id,
        "nombre_usuario": "daniela.torres",
    }

    recuperada = gerente.post(f"{ASISTENTES}/{asistente_id}/recuperacion").json()

    assert recuperada["nombre_usuario"] == "daniela.torres"
    assert recuperada["contrasena_temporal"] != creada["contrasena_temporal"]
    sesion = ingresar(TestClient(gerente.app), "daniela.torres", recuperada["contrasena_temporal"])
    assert "completar_datos" in sesion["pasos_pendientes"]
    acciones = consultar(
        base_de(gerente),
        "SELECT accion FROM auditoria WHERE accion IN ('CUENTA_ELIMINADA', 'CUENTA_RECUPERADA')"
        " ORDER BY id",
    )
    assert acciones == [("CUENTA_ELIMINADA",), ("CUENTA_RECUPERADA",)]


def test_puede_crear_una_cuenta_nueva_en_lugar_de_recuperarla(gerente: TestClient) -> None:
    anterior = registrar(gerente)["asistente"]["id"]
    gerente.post(f"{ASISTENTES}/{anterior}/eliminacion")

    nueva = registrar(gerente, crear_aunque_eliminada=True)

    assert nueva["asistente"]["id"] != anterior
    assert nueva["nombre_usuario"] == "daniela.torres2"
    # Ya hay otra cuenta vigente con su documento: la eliminada no se puede recuperar.
    conflicto = gerente.post(f"{ASISTENTES}/{anterior}/recuperacion")
    assert conflicto.status_code == 409


def test_solo_el_gerente_administra_y_solo_su_equipo(cliente: TestClient, equipo: Equipo) -> None:
    habilitar(base_de(cliente), equipo.asistente.id, equipo.otro_gerente.id)
    ingresar(cliente, equipo.asistente.usuario, equipo.asistente.contrasena)
    assert cliente.get(ASISTENTES).json()["code"] == "SIN_PERMISO"
    assert cliente.post(ASISTENTES, json=DANIELA).status_code == 403

    ingresar(cliente, equipo.otro_gerente.usuario, equipo.otro_gerente.contrasena)
    ajena = f"{ASISTENTES}/{equipo.asistente.id}"
    assert cliente.post(f"{ajena}/bloqueo").json()["code"] == "CUENTA_NO_ENCONTRADA"
    assert cliente.post(f"{ajena}/eliminacion").status_code == 404
    assert cliente.get(ASISTENTES).json() == []


def test_el_gerente_debe_completar_su_incorporacion(cliente: TestClient, equipo: Equipo) -> None:
    ingresar(cliente, equipo.gerente.usuario, equipo.gerente.contrasena)
    assert cliente.get(ASISTENTES).json()["code"] == "INCORPORACION_PENDIENTE"


def test_la_asistente_no_trabaja_hasta_confirmar_sus_datos(gerente: TestClient) -> None:
    creada = registrar(gerente)
    asistente = TestClient(gerente.app)
    ingresar(asistente, "daniela.torres", creada["contrasena_temporal"])
    vigentes = asistente.get("/api/v1/documentos-legales").json()
    temprano = asistente.post(CONFIRMACION, json={**DANIELA, "correo": "dani@ejemplo.pe"})
    asistente.post(
        "/api/v1/documentos-legales/aceptacion",
        json={"documentos": [{"tipo": d["tipo"], "version": d["version"]} for d in vigentes]},
    )

    bloqueada = asistente.get("/api/v1/espacio").json()
    sin_correo = asistente.post(CONFIRMACION, json={**DANIELA, "correo": ""})
    # Corrige el documento que su gerente escribió mal.
    confirmada = asistente.post(
        CONFIRMACION, json={**DANIELA, "numero_documento": "44556678", "correo": "Dani@Ejemplo.pe"}
    )

    assert temprano.json()["code"] == "INCORPORACION_PENDIENTE"
    assert bloqueada["code"] == "INCORPORACION_PENDIENTE"
    assert bloqueada["pending_steps"] == ["completar_datos"]
    assert sin_correo.json()["fields"]["correo"] == "Ingresa tu correo."
    assert confirmada.status_code == 200, confirmada.json()
    assert confirmada.json()["pasos_pendientes"] == []
    assert asistente.get("/api/v1/espacio").status_code == 200
    cuenta = asistente.get("/api/v1/cuenta").json()
    assert (cuenta["correo"], cuenta["numero_documento"]) == ("dani@ejemplo.pe", "44556678")
    otra_vez = asistente.post(CONFIRMACION, json={**DANIELA, "correo": "dani@ejemplo.pe"})
    assert otra_vez.json()["code"] == "DATOS_YA_CONFIRMADOS"
    estados = {a["id"]: a["estado"] for a in gerente.get(ASISTENTES).json()}
    assert estados[creada["asistente"]["id"]] == "activa"


def test_cinco_intentos_bloquean_a_la_asistente_registrada_hasta_que_la_desbloqueen(
    gerente: TestClient,
) -> None:
    creada = registrar(gerente)
    otra = TestClient(gerente.app)
    intentos = [
        otra.post(LOGIN, json={"nombre_usuario": "daniela.torres", "contrasena": "Incorrecta123"})
        for _ in range(5)
    ]
    correcta = {"nombre_usuario": "daniela.torres", "contrasena": creada["contrasena_temporal"]}

    assert [r.status_code for r in intentos] == [401, 401, 401, 401, 423]
    assert otra.post(LOGIN, json=correcta).status_code == 423
    causas = {a["id"]: a["causa_bloqueo"] for a in gerente.get(ASISTENTES).json()}
    assert causas[creada["asistente"]["id"]] == "intentos_fallidos"
    gerente.post(f"{ASISTENTES}/{creada['asistente']['id']}/desbloqueo")
    assert otra.post(LOGIN, json=correcta).status_code == 200


def test_limita_la_frecuencia_de_la_gestion_del_equipo(
    crear_cliente: FabricaCliente, equipo: Equipo
) -> None:
    cliente = crear_cliente(limite_gestion_equipo=2)
    habilitar(base_de(cliente), equipo.gerente.id)
    ingresar(cliente, equipo.gerente.usuario, equipo.gerente.contrasena)

    codigos = [cliente.post(ASISTENTES, json=DANIELA).status_code for _ in range(3)]

    assert codigos == [201, 409, 429]
