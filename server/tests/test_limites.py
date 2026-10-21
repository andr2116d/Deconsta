from unittest.mock import patch

from fastapi.testclient import TestClient
from redis import RedisError

from tests.conftest import Equipo, FabricaCliente

LOGIN = "/api/v1/auth/login"


def intento(cliente: TestClient, usuario: str, contrasena: str = "Incorrecta123"):
    return cliente.post(LOGIN, json={"nombre_usuario": usuario, "contrasena": contrasena})


def test_limita_los_intentos_por_origen_con_retry_after(
    crear_cliente: FabricaCliente, equipo: Equipo
) -> None:
    cliente = crear_cliente(limite_ingreso_por_origen=3, ventana_ingreso_por_origen_segundos=60)
    for usuario in ("uno.x", "dos.x", "tres.x"):
        assert intento(cliente, usuario).status_code == 401

    respuesta = intento(cliente, "cuatro.x")

    assert respuesta.status_code == 429
    assert respuesta.json()["code"] == "DEMASIADAS_SOLICITUDES"
    assert 0 < int(respuesta.headers["retry-after"]) <= 60
    assert respuesta.json()["retry_after"] == int(respuesta.headers["retry-after"])


def test_el_limite_por_usuario_no_se_elude_con_clientes_nuevos(
    crear_cliente: FabricaCliente, equipo: Equipo
) -> None:
    cliente = crear_cliente(limite_ingreso_por_usuario=3)
    gerente = equipo.gerente
    for _ in range(3):
        # Cada intento con un cliente nuevo: sin cookies ni sesión previa.
        assert intento(TestClient(cliente.app), gerente.usuario).status_code == 401

    respuesta = intento(TestClient(cliente.app), gerente.usuario, gerente.contrasena)
    assert respuesta.status_code == 429


def test_la_limitacion_rechaza_antes_de_contar_intentos_para_el_bloqueo(
    crear_cliente: FabricaCliente, equipo: Equipo
) -> None:
    # Con el límite alcanzado, los intentos extra no llegan a la base y no bloquean a la asistente.
    cliente = crear_cliente(limite_ingreso_por_usuario=3)
    asistente = equipo.asistente
    estados = [intento(cliente, asistente.usuario).status_code for _ in range(6)]
    assert estados == [401, 401, 401, 429, 429, 429]

    cliente.app.state.contenedor.redis.flushdb()  # type: ignore[attr-defined]
    assert intento(cliente, asistente.usuario, asistente.contrasena).status_code == 200


def test_si_redis_no_responde_el_ingreso_se_rechaza(cliente: TestClient, equipo: Equipo) -> None:
    with patch("redis.commands.core.Script.__call__", side_effect=RedisError("caído")):
        respuesta = intento(cliente, equipo.gerente.usuario, equipo.gerente.contrasena)

    assert respuesta.status_code == 503
    assert respuesta.json()["code"] == "SERVICIO_NO_DISPONIBLE"
    assert "caído" not in respuesta.text
