import uuid

import pytest
from fastapi.testclient import TestClient

from tests.conftest import Equipo, consultar

LOGIN = "/api/v1/auth/login"
CONTRASENA = "/api/v1/auth/contrasena"
NUEVA = "Ciruela-Rosa-2026"


def ingresar(cliente: TestClient, usuario: str, contrasena: str) -> dict:
    respuesta = cliente.post(LOGIN, json={"nombre_usuario": usuario, "contrasena": contrasena})
    assert respuesta.status_code == 200, respuesta.json()
    return respuesta.json()


def desbloquear(cliente: TestClient, asistente_id: uuid.UUID, motivo: str | None = None):
    return cliente.post(f"/api/v1/asistentes/{asistente_id}/desbloqueo", json={"motivo": motivo})


def bloquear(cliente: TestClient, usuario: str) -> None:
    for _ in range(5):
        cliente.post(LOGIN, json={"nombre_usuario": usuario, "contrasena": "Incorrecta123"})


def base_de(cliente: TestClient) -> str:
    return cliente.app.state.contenedor.config.database_url  # type: ignore[attr-defined]


def test_cambiar_la_contrasena_inicial_apaga_el_recordatorio(
    cliente: TestClient, equipo: Equipo
) -> None:
    asistente = equipo.asistente
    ingresar(cliente, asistente.usuario, asistente.contrasena)

    respuesta = cliente.post(
        CONTRASENA, json={"contrasena_actual": asistente.contrasena, "contrasena_nueva": NUEVA}
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["debe_cambiar_contrasena"] is False
    assert cliente.get("/api/v1/auth/me").status_code == 200
    siguiente = TestClient(cliente.app)
    assert ingresar(siguiente, asistente.usuario, NUEVA)["debe_cambiar_contrasena"] is False
    assert (
        siguiente.post(
            LOGIN, json={"nombre_usuario": asistente.usuario, "contrasena": asistente.contrasena}
        ).status_code
        == 401
    )
    eventos = consultar(
        base_de(cliente),
        "SELECT detalle->>'era_inicial' FROM auditoria WHERE accion = 'CONTRASENA_CAMBIADA'",
    )
    assert eventos == [("true",)]


def test_cambiar_la_contrasena_cierra_las_demas_sesiones(
    cliente: TestClient, equipo: Equipo
) -> None:
    gerente = equipo.gerente
    otra_sesion = TestClient(cliente.app)
    ingresar(otra_sesion, gerente.usuario, gerente.contrasena)
    ingresar(cliente, gerente.usuario, gerente.contrasena)

    cliente.post(
        CONTRASENA, json={"contrasena_actual": gerente.contrasena, "contrasena_nueva": NUEVA}
    )

    assert cliente.get("/api/v1/auth/me").status_code == 200
    assert otra_sesion.get("/api/v1/auth/me").status_code == 401


@pytest.mark.parametrize(
    ("actual", "nueva", "estado", "codigo"),
    [
        ("Equivocada123", NUEVA, 400, "CONTRASENA_ACTUAL_INCORRECTA"),
        (None, "corta1", 422, "CONTRASENA_INSEGURA"),
        (None, None, 422, "CONTRASENA_REPETIDA"),
    ],
)
def test_rechaza_cambios_de_contrasena_invalidos(
    cliente: TestClient,
    equipo: Equipo,
    actual: str | None,
    nueva: str | None,
    estado: int,
    codigo: str,
) -> None:
    gerente = equipo.gerente
    ingresar(cliente, gerente.usuario, gerente.contrasena)

    respuesta = cliente.post(
        CONTRASENA,
        json={
            "contrasena_actual": actual or gerente.contrasena,
            "contrasena_nueva": nueva or gerente.contrasena,
        },
    )

    assert respuesta.status_code == estado
    assert respuesta.json()["code"] == codigo
    assert respuesta.json()["fields"]
    assert cliente.get("/api/v1/auth/me").json()["debe_cambiar_contrasena"] is True


def test_la_politica_explica_cada_requisito_incumplido(cliente: TestClient, equipo: Equipo) -> None:
    gerente = equipo.gerente
    ingresar(cliente, gerente.usuario, gerente.contrasena)

    respuesta = cliente.post(
        CONTRASENA,
        json={"contrasena_actual": gerente.contrasena, "contrasena_nueva": f"{gerente.usuario}xx"},
    )

    assert set(respuesta.json()["requirements"]) == {"SIN_NUMERO", "CONTIENE_USUARIO"}


def test_cambiar_la_contrasena_exige_sesion(cliente: TestClient) -> None:
    respuesta = cliente.post(CONTRASENA, json={"contrasena_actual": "a", "contrasena_nueva": "b"})
    assert respuesta.status_code == 401


def test_el_gerente_desbloquea_a_su_asistente(cliente: TestClient, equipo: Equipo) -> None:
    bloquear(cliente, equipo.asistente.usuario)
    ingresar(cliente, equipo.gerente.usuario, equipo.gerente.contrasena)

    respuesta = desbloquear(cliente, equipo.asistente.id, "Confirmó por teléfono que fue ella")

    assert respuesta.status_code == 200
    assert respuesta.json()["bloqueada"] is False
    ingresar(TestClient(cliente.app), equipo.asistente.usuario, equipo.asistente.contrasena)
    assert consultar(
        base_de(cliente),
        "SELECT actor_id, motivo FROM auditoria WHERE accion = 'CUENTA_DESBLOQUEADA'",
    ) == [(equipo.gerente.id, "Confirmó por teléfono que fue ella")]
    # Desbloquear dos veces no es una operación válida.
    assert desbloquear(cliente, equipo.asistente.id).json()["code"] == "CUENTA_NO_BLOQUEADA"


def test_el_desbloqueo_tras_un_bloqueo_reinicia_el_contador(
    cliente: TestClient, equipo: Equipo
) -> None:
    bloquear(cliente, equipo.asistente.usuario)
    gerente = TestClient(cliente.app)
    ingresar(gerente, equipo.gerente.usuario, equipo.gerente.contrasena)
    desbloquear(gerente, equipo.asistente.id)

    for _ in range(4):
        cliente.post(LOGIN, json={"nombre_usuario": equipo.asistente.usuario, "contrasena": "x1"})
    ingresar(cliente, equipo.asistente.usuario, equipo.asistente.contrasena)


def test_otro_gerente_no_puede_desbloquear_ni_saber_si_existe(
    cliente: TestClient, equipo: Equipo
) -> None:
    bloquear(cliente, equipo.asistente.usuario)
    ingresar(cliente, equipo.otro_gerente.usuario, equipo.otro_gerente.contrasena)

    ajena = desbloquear(cliente, equipo.asistente.id)
    inexistente = desbloquear(cliente, uuid.uuid4())

    assert ajena.status_code == inexistente.status_code == 404
    assert ajena.json() == inexistente.json()


def test_una_asistente_no_puede_desbloquear(cliente: TestClient, equipo: Equipo) -> None:
    ingresar(cliente, equipo.asistente.usuario, equipo.asistente.contrasena)
    respuesta = desbloquear(cliente, equipo.asistente.id)
    assert respuesta.status_code == 403
    assert respuesta.json()["code"] == "SIN_PERMISO"


def test_desbloquear_sin_sesion_responde_no_autenticado(
    cliente: TestClient, equipo: Equipo
) -> None:
    assert desbloquear(cliente, equipo.asistente.id).status_code == 401
