import csv
import io
from dataclasses import replace
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from tests.conftest import Equipo
from tests.test_categorias import sesion
from tests.test_documentos import LEIDO, dobles
from tests.test_pagos import PAGOS, comprobante, deuda_de, hoy, pagar, voucher

HISTORIAL = "/api/v1/historial"


@pytest.fixture
def gerente(cliente: TestClient, equipo: Equipo) -> TestClient:
    dobles(cliente).revisor.datos = LEIDO
    return sesion(cliente, equipo.gerente)


@pytest.fixture
def asistente(cliente: TestClient, equipo: Equipo, gerente: TestClient) -> TestClient:
    return sesion(cliente, equipo.asistente)


def otra(cliente: TestClient, semilla: int, periodo: str, **cambios: object) -> dict:
    """Otra deuda del espacio: el periodo distinto evita que se tome por el mismo recibo."""
    dobles(cliente).revisor.datos = replace(LEIDO, periodo=periodo)
    return deuda_de(cliente, semilla, **cambios)


def pagada(asistente: TestClient, gerente: TestClient, semilla: int) -> dict:
    deuda = otra(gerente, semilla, "2026-06")
    voucher(asistente, numero_operacion=f"09{semilla:06d}")
    pago = pagar(asistente, deuda["id"], comprobante(asistente, deuda["id"], 400 + semilla)["id"])
    assert pago.status_code == 201, pago.json()
    return {**deuda, "pago": pago.json()}


def test_el_historial_cuenta_quien_hizo_que_y_la_confianza_es_del_gerente(
    asistente: TestClient, gerente: TestClient
) -> None:
    deuda = pagada(asistente, gerente, 1)
    gerente.post(f"{PAGOS}/{deuda['pago']['id']}/confirmacion")

    [item] = gerente.get(HISTORIAL).json()["deudas"]

    assert (item["id"], item["estado"], item["registrada_por"]) == (
        deuda["id"],
        "registrada",
        "Valentina Ramos",
    )
    assert item["cuotas"] == [
        {
            "numero": 1,
            "vence_el": item["cuotas"][0]["vence_el"],
            "importe": "182.40",
            "pago": "confirmado",
            "mora": None,
        }
    ]
    [pago] = item["pagos"]
    assert (pago["registrado_por"], pago["estado"]) == ("Lucía Vega", "confirmado")
    assert pago["confianza"] is not None
    assert [(e["accion"], e["actor"], e["cuota"]) for e in item["eventos"]] == [
        ("DEUDA_REGISTRADA", "Valentina Ramos", None),
        ("PAGO_REGISTRADO", "Lucía Vega", 1),
        ("PAGO_CONFIRMADO", "Valentina Ramos", 1),
    ]
    # Todo el espacio ve el historial; la confianza, solo el gerente.
    [visto] = asistente.get(HISTORIAL).json()["deudas"]
    assert visto["pagos"][0]["confianza"] is None


def test_filtra_por_estado_texto_lugar_y_mis_registros(
    asistente: TestClient, gerente: TestClient, equipo: Equipo
) -> None:
    pagada(asistente, gerente, 2)
    agua = otra(asistente, 3, "2026-05", concepto="Agua de la oficina")
    otra(gerente, 4, "2026-04", concepto="Internet fibra", lugares_pago=["ventanilla"])

    def conceptos(cliente: TestClient, **filtros: object) -> list[str]:
        respuesta = cliente.get(HISTORIAL, params=filtros)
        assert respuesta.status_code == 200, respuesta.json()
        return [d["concepto"] for d in respuesta.json()["deudas"]]

    assert conceptos(gerente, estado="por_verificar") == ["Luz de la casa"]
    assert conceptos(gerente, q="oficina") == ["Agua de la oficina"]
    # El % no es un comodín.
    assert conceptos(gerente, q="%") == []
    assert conceptos(gerente, lugar_pago="ventanilla") == ["Internet fibra"]
    assert conceptos(gerente, registrada_por=str(equipo.asistente.id)) == [agua["concepto"]]
    assert conceptos(gerente, pagado_por=str(equipo.asistente.id)) == ["Luz de la casa"]
    # Mis registros: lo que la asistente registró o pagó.
    assert conceptos(asistente, mios="true") == ["Agua de la oficina", "Luz de la casa"]
    assert conceptos(gerente, estado="mora") == []


def test_pagina_con_cursor_y_valida_el_rango(gerente: TestClient) -> None:
    for semilla, periodo in ((5, "2026-03"), (6, "2026-02"), (7, "2026-01")):
        otra(gerente, semilla, periodo)

    primera = gerente.get(HISTORIAL, params={"limite": 2}).json()
    segunda = gerente.get(HISTORIAL, params={"limite": 2, "cursor": primera["siguiente"]}).json()

    assert len(primera["deudas"]) == 2 and primera["siguiente"]
    assert len(segunda["deudas"]) == 1 and segunda["siguiente"] is None
    ids = [d["id"] for d in primera["deudas"] + segunda["deudas"]]
    assert len(set(ids)) == 3
    assert (primera["hasta"], primera["desde"]) == (
        hoy().isoformat(),
        (hoy() - timedelta(days=89)).isoformat(),
    )
    # Fuera del rango no aparece.
    pasado = {"desde": "2025-01-01", "hasta": "2025-01-31"}
    assert gerente.get(HISTORIAL, params=pasado).json()["deudas"] == []
    largo = gerente.get(HISTORIAL, params={"desde": "2025-01-01", "hasta": "2026-06-30"})
    assert (largo.status_code, set(largo.json()["fields"])) == (422, {"desde"})
    al_reves = gerente.get(HISTORIAL, params={"desde": "2026-02-01", "hasta": "2026-01-01"})
    assert al_reves.status_code == 422
    malo = gerente.get(HISTORIAL, params={"cursor": "no-es-un-cursor"})
    assert (malo.status_code, set(malo.json()["fields"])) == (422, {"cursor"})


def test_solo_el_gerente_exporta_el_csv_sin_datos_cifrados(
    asistente: TestClient, gerente: TestClient
) -> None:
    deuda = pagada(asistente, gerente, 8)
    # Un motivo que una hoja de cálculo ejecutaría como fórmula.
    gerente.post(f"{PAGOS}/{deuda['pago']['id']}/devolucion", json={"motivo": "=HIPERVINCULO(x)"})

    assert asistente.get(f"{HISTORIAL}/exportacion").status_code == 403
    respuesta = gerente.get(f"{HISTORIAL}/exportacion")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    assert "attachment" in respuesta.headers["content-disposition"]
    [fila] = list(csv.DictReader(io.StringIO(respuesta.text.lstrip("\ufeff"))))
    assert (fila["concepto"], fila["estado_pago"], fila["importe_pagado"]) == (
        "Luz de la casa",
        "devuelto",
        "182.40",
    )
    assert (fila["registrada_por"], fila["pagado_por"]) == ("valentina.ramos", "lucia.vega")
    assert fila["motivo_decision_pago"] == "'=HIPERVINCULO(x)"
    # Ni el titular ni el código de pago salen del espacio.
    assert "54871236" not in respuesta.text
    assert "Valentina Ramos Díaz" not in respuesta.text
