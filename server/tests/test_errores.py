import logging

import pytest
from fastapi.testclient import TestClient

from tests.conftest import Equipo


def test_un_error_interno_no_expone_detalles_y_queda_registrado(
    cliente: TestClient, equipo: Equipo, caplog: pytest.LogCaptureFixture
) -> None:
    contenedor = cliente.app.state.contenedor  # type: ignore[attr-defined]

    def fallar(*_: object) -> None:
        raise RuntimeError("password=secreta host=db.interno")

    contenedor.iniciar_sesion.ejecutar = fallar
    with caplog.at_level(logging.ERROR, logger="app"):
        respuesta = cliente.post(
            "/api/v1/auth/login", json={"nombre_usuario": "ana", "contrasena": "Secreta123"}
        )

    assert respuesta.status_code == 500
    cuerpo = respuesta.json()
    assert cuerpo["code"] == "ERROR_INTERNO"
    assert cuerpo["reference"] == respuesta.headers["x-request-id"]
    assert "secreta" not in respuesta.text and "interno" not in respuesta.text
    assert "Secreta123" not in caplog.text
    assert any(cuerpo["reference"] == getattr(r, "id_solicitud", None) for r in caplog.records)


def test_una_ruta_inexistente_usa_la_estructura_comun(cliente: TestClient) -> None:
    respuesta = cliente.get("/api/v1/no-existe")
    assert respuesta.status_code == 404
    assert respuesta.json() == {"code": "NO_ENCONTRADO", "detail": "No encontramos lo que buscas."}


def test_las_respuestas_llevan_cabeceras_de_seguridad(cliente: TestClient) -> None:
    respuesta = cliente.get("/health")
    assert respuesta.headers["x-content-type-options"] == "nosniff"
    assert respuesta.headers["x-frame-options"] == "DENY"


INVISIBLES = "Quita los caracteres invisibles o de control que tiene este texto."


@pytest.mark.parametrize("usuario", ["ro\x00sa", "rosa‮", "ro​sa"])
def test_rechaza_caracteres_de_control_sin_llegar_a_la_base(
    cliente: TestClient, usuario: str
) -> None:
    # El carácter nulo hacía fallar a Postgres con un error 500 antes de iniciar sesión.
    respuesta = cliente.post(
        "/api/v1/auth/login", json={"nombre_usuario": usuario, "contrasena": "Secreta123"}
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["fields"] == {"nombre_usuario": INVISIBLES}


def test_rechaza_caracteres_de_control_en_textos_libres(
    cliente: TestClient, equipo: Equipo
) -> None:
    from tests.test_categorias import sesion

    gerente = sesion(cliente, equipo.gerente)
    descripcion = gerente.post("/api/v1/categorias", json={"nombre": "Luz", "descripcion": "a\x00"})
    motivo = gerente.post(
        f"/api/v1/asistentes/{equipo.asistente.id}/bloqueo", json={"motivo": "Vacaciones‮"}
    )

    assert descripcion.json()["fields"] == {"descripcion": INVISIBLES}
    assert motivo.json()["fields"] == {"motivo": INVISIBLES}


def test_rechaza_un_cuerpo_demasiado_grande(cliente: TestClient) -> None:
    grande = {"nombre_usuario": "a" * 70_000, "contrasena": "x"}
    declarado = cliente.post("/api/v1/auth/login", json=grande)

    def por_partes():
        yield b'{"nombre_usuario": "'
        for _ in range(80):
            yield b"a" * 1024
        yield b'"}'

    sin_tamano = cliente.post(
        "/api/v1/auth/login", content=por_partes(), headers={"Content-Type": "application/json"}
    )

    for respuesta in (declarado, sin_tamano):
        assert respuesta.status_code == 413
        assert respuesta.json()["code"] == "CUERPO_DEMASIADO_GRANDE"
        assert respuesta.headers["x-content-type-options"] == "nosniff"


def test_los_errores_de_la_base_no_registran_los_valores_de_la_consulta() -> None:
    from app.core.database import crear_motor

    assert crear_motor("postgresql+psycopg://u:p@localhost/x").hide_parameters is True


def test_cerrar_sesion_borra_la_cookie_con_sus_mismos_atributos(
    cliente: TestClient, equipo: Equipo
) -> None:
    from tests.test_contrasena_y_desbloqueo import ingresar

    ingresar(cliente, equipo.gerente.usuario, equipo.gerente.contrasena)
    cookie = cliente.post("/api/v1/auth/logout").headers["set-cookie"]

    assert "Max-Age=0" in cookie
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/api" in cookie
