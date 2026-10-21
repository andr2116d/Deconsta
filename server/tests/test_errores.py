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
