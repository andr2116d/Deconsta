import pytest
from fastapi.testclient import TestClient

from tests.conftest import Equipo
from tests.test_categorias import sesion
from tests.test_documentos import LEIDO, dobles
from tests.test_historial import otra, pagada
from tests.test_pagos import PAGOS

PANEL = "/api/v1/panel"


@pytest.fixture
def gerente(cliente: TestClient, equipo: Equipo) -> TestClient:
    dobles(cliente).revisor.datos = LEIDO
    return sesion(cliente, equipo.gerente)


@pytest.fixture
def asistente(cliente: TestClient, equipo: Equipo, gerente: TestClient) -> TestClient:
    return sesion(cliente, equipo.asistente)


def escenario(asistente: TestClient, gerente: TestClient) -> tuple[dict, dict, dict]:
    """Un pago por verificar, una deuda por pagar y una deuda que espera autorización."""
    pagada_ = pagada(asistente, gerente, 1)
    por_pagar = otra(gerente, 2, "2026-05", concepto="Agua de la casa")
    gerente.post("/api/v1/reglas/limite", json={"limite_importe": "100.00"})
    por_autorizar = otra(asistente, 3, "2026-04", concepto="Internet de la casa")
    assert por_autorizar["estado"] == "por_autorizar"
    return pagada_, por_pagar, por_autorizar


def test_el_resumen_del_gerente_trae_lo_que_espera_su_decision(
    asistente: TestClient,
    gerente: TestClient,
) -> None:
    pagada_, por_pagar, por_autorizar = escenario(asistente, gerente)

    respuesta = gerente.get(PANEL)

    assert respuesta.status_code == 200, respuesta.json()
    panel = respuesta.json()
    assert (panel["rol"], panel["jornada"]) == ("gerente", None)
    resumen = panel["resumen"]
    assert (resumen["por_pagar"], resumen["cuotas_por_pagar"]) == ("182.40", 1)
    assert (resumen["pagado_mes"], resumen["pagos_mes"]) == ("182.40", 1)
    assert {(p["tipo"], p["deuda_id"], p["por"]) for p in resumen["pendientes"]} == {
        ("verificar_pago", pagada_["id"], "Lucía Vega"),
        ("autorizar_deuda", por_autorizar["id"], "Lucía Vega"),
    }
    [proxima] = resumen["proximas"]
    assert (proxima["deuda_id"], proxima["pedido"]) == (por_pagar["id"], None)


def test_la_jornada_de_la_asistente_empieza_por_lo_que_le_pidieron(
    asistente: TestClient,
    gerente: TestClient,
    equipo: Equipo,
) -> None:
    _, por_pagar, _ = escenario(asistente, gerente)
    sin_pedido = asistente.get(PANEL).json()["jornada"]
    assert sin_pedido["siguiente"]["pedido"] is None
    gerente.post(
        f"{PAGOS}/pedidos",
        json={
            "deuda_id": por_pagar["id"],
            "cuota": 1,
            "asistente_id": str(equipo.asistente.id),
            "nota": "Antes del corte.",
        },
    )

    panel = asistente.get(PANEL).json()

    assert (panel["rol"], panel["resumen"]) == ("asistente", None)
    jornada = panel["jornada"]
    # Lo suyo que espera al gerente: la deuda por autorizar y el pago por verificar.
    assert (jornada["por_completar"], jornada["en_manos_del_gerente"]) == (1, 2)
    assert (jornada["gerente"], jornada["limite"]) == ("Valentina Ramos", "100.00")
    siguiente = jornada["siguiente"]
    assert (siguiente["deuda_id"], siguiente["pedido"]["nota"]) == (
        por_pagar["id"],
        "Antes del corte.",
    )


def test_el_panel_exige_sesion(cliente: TestClient) -> None:
    respuesta = cliente.get(PANEL)

    assert (respuesta.status_code, respuesta.json()["code"]) == (401, "NO_AUTENTICADO")
