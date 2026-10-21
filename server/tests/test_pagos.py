from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from app.deudas.dominio.modelos import LugarPago
from tests.conftest import Equipo
from tests.dobles import TEXTO_VOUCHER, VOUCHER, imagen
from tests.test_categorias import sesion
from tests.test_deudas import DEUDAS, notificaciones, nueva
from tests.test_documentos import LEIDO, dobles

PAGOS = "/api/v1/pagos"
COMPROBANTES = f"{PAGOS}/comprobantes"


def hoy() -> date:
    return datetime.now(ZoneInfo("America/Lima")).date()


@pytest.fixture
def gerente(cliente: TestClient, equipo: Equipo) -> TestClient:
    dobles(cliente).revisor.datos = LEIDO
    dobles(cliente).revisor.comprobante = replace(VOUCHER, pagado_el=hoy())
    return sesion(cliente, equipo.gerente)


@pytest.fixture
def asistente(cliente: TestClient, equipo: Equipo, gerente: TestClient) -> TestClient:
    return sesion(cliente, equipo.asistente)


def voucher(cliente: TestClient, **cambios: Any) -> None:
    """Lo que leerán el OCR y la IA del próximo comprobante: el texto leído trae el importe, la
    operación y el código que lee la IA."""
    datos = replace(VOUCHER, **{"pagado_el": hoy(), **cambios})
    texto = TEXTO_VOUCHER
    for original, nuevo in (
        (VOUCHER.importe, datos.importe),
        (VOUCHER.numero_operacion, datos.numero_operacion),
        (VOUCHER.codigo_pago, datos.codigo_pago),
    ):
        texto = texto.replace(str(original), str(nuevo or ""))
    dobles(cliente).lector.texto = texto
    dobles(cliente).revisor.comprobante = datos


def subir(cliente: TestClient, deuda_id: str, semilla: int, cuota: int = 1) -> httpx.Response:
    return cliente.post(
        COMPROBANTES,
        files={"archivo": ("voucher.png", imagen(semilla), "image/png")},
        data={"deuda_id": deuda_id, "cuota": str(cuota)},
    )


def comprobante(cliente: TestClient, deuda_id: str, semilla: int, cuota: int = 1) -> dict:
    respuesta = subir(cliente, deuda_id, semilla, cuota)
    assert respuesta.status_code == 202, respuesta.json()
    return cliente.get(f"{COMPROBANTES}/{respuesta.json()['id']}").json()


def pagar(cliente: TestClient, deuda_id: str, *ids: str, cuota: int = 1) -> httpx.Response:
    return cliente.post(PAGOS, json={"deuda_id": deuda_id, "cuota": cuota, "comprobantes": ids})


def deuda_de(cliente: TestClient, semilla: int, **cambios: Any) -> dict:
    """Una deuda registrada de Hidrandina por S/ 182.40 que se paga en agentes."""
    dobles(cliente).lector.texto = dobles(cliente).lector.__class__().texto
    return nueva(cliente, semilla, **cambios)["deuda"]


def test_la_asistente_paga_con_su_voucher_y_el_gerente_recibe_la_confianza(
    cliente: TestClient, asistente: TestClient, gerente: TestClient, equipo: Equipo
) -> None:
    deuda = deuda_de(gerente, 1)
    rosa = sesion(cliente, equipo.otra_asistente)
    # Cualquier asistente del espacio paga cualquier deuda registrada, también la del gerente.
    por_pagar = rosa.get(f"{PAGOS}/por-pagar").json()
    assert [(c["deuda_id"], c["cuota"], c["importe"]) for c in por_pagar["cuotas"]] == [
        (deuda["id"], 1, "182.40")
    ]
    voucher(rosa)
    leido = comprobante(rosa, deuda["id"], 101)
    assert (leido["estado"], leido["senales"]) == ("listo", [])
    assert leido["lectura"]["importe"] == "182.40"

    respuesta = pagar(rosa, deuda["id"], leido["id"])

    assert respuesta.status_code == 201, respuesta.json()
    pago = respuesta.json()
    assert (pago["estado"], pago["importe"], pago["lugar_pago"]) == (
        "por_verificar",
        "182.40",
        "agente",
    )
    # La confianza es para el gerente: a la asistente no se le dice qué comprobaciones pasó.
    assert (pago["confianza"], pago["comprobaciones"]) == (None, None)
    [por_verificar] = gerente.get(PAGOS, params={"estado": "por_verificar"}).json()
    assert 0 < por_verificar["confianza"] <= 95
    codigos = {c["codigo"] for c in por_verificar["comprobaciones"]}
    assert codigos >= {"importe", "codigo_pago", "fecha"}
    [aviso] = [n for n in notificaciones(gerente) if n["tipo"] == "PAGO_POR_VERIFICAR"]
    assert f"{por_verificar['confianza']} %" in aviso["cuerpo"]
    # La cuota ya no falta pagarse y la deuda no se anula mientras el pago espera.
    assert rosa.get(f"{PAGOS}/por-pagar").json()["cuotas"] == []
    detalle = gerente.get(f"{DEUDAS}/{deuda['id']}").json()
    assert detalle["cuotas"][0]["pago"] == "por_verificar"
    anular = gerente.post(f"{DEUDAS}/{deuda['id']}/anulacion", json={"motivo": "No"})
    assert (anular.status_code, anular.json()["code"]) == (409, "ESTADO_NO_PERMITE")
    otra_vez = pagar(rosa, deuda["id"], leido["id"])
    assert (otra_vez.status_code, otra_vez.json()["code"]) == (409, "CUOTA_YA_PAGADA")


def test_el_pago_del_gerente_queda_confirmado_sin_avisarse(gerente: TestClient) -> None:
    deuda = deuda_de(gerente, 2)
    voucher(gerente)
    leido = comprobante(gerente, deuda["id"], 102)

    pago = pagar(gerente, deuda["id"], leido["id"]).json()

    assert pago["estado"] == "confirmado"
    assert not [n for n in notificaciones(gerente) if n["tipo"] == "PAGO_POR_VERIFICAR"]
    assert gerente.get(f"{DEUDAS}/{deuda['id']}").json()["vencida_hace"] is None


def test_un_agente_que_cobra_por_partes_se_registra_con_todos_sus_vouchers(
    asistente: TestClient, gerente: TestClient
) -> None:
    deuda = deuda_de(gerente, 3)
    voucher(asistente, importe=Decimal("100.00"), numero_operacion="0458214")
    primera = comprobante(asistente, deuda["id"], 103)
    assert [s["codigo"] for s in primera["senales"]] == ["PAGO_PARCIAL"]
    sola = pagar(asistente, deuda["id"], primera["id"])
    assert (sola.status_code, sola.json()["code"]) == (422, "IMPORTE_NO_COINCIDE")
    assert "falta S/" in sola.json()["detail"].replace("\xa0", " ")
    voucher(asistente, importe=Decimal("82.40"), numero_operacion="0458215")
    segunda = comprobante(asistente, deuda["id"], 104)

    pago = pagar(asistente, deuda["id"], primera["id"], segunda["id"])

    assert pago.status_code == 201, pago.json()
    assert (pago.json()["importe"], len(pago.json()["comprobantes"])) == ("182.40", 2)


def test_por_partes_solo_en_un_agente_y_el_mismo_dia(
    asistente: TestClient, gerente: TestClient
) -> None:
    deuda = deuda_de(gerente, 4, lugares_pago=["agente", "billetera"])
    voucher(asistente, importe=Decimal("100.00"), numero_operacion="0458221")
    en_agente = comprobante(asistente, deuda["id"], 105)
    voucher(
        asistente,
        importe=Decimal("82.40"),
        numero_operacion="0458222",
        pagado_el=hoy() - timedelta(days=1),
    )
    # La deuda se registró hoy: un voucher de ayer no puede ser su pago.
    de_ayer = comprobante(asistente, deuda["id"], 106)
    assert de_ayer["estado"] == "rechazado"
    assert "FECHA_ANTERIOR_A_LA_DEUDA" in {s["codigo"] for s in de_ayer["senales"]}
    # Por Yape no se paga por partes: menos que la cuota no corresponde.
    voucher(
        asistente, importe=Decimal("82.40"), numero_operacion="0458223", lugar=LugarPago.BILLETERA
    )
    por_yape = comprobante(asistente, deuda["id"], 107)
    assert por_yape["estado"] == "rechazado"
    assert "MONTO_MENOR" in {s["codigo"] for s in por_yape["senales"]}
    assert pagar(asistente, deuda["id"], en_agente["id"]).json()["code"] == "IMPORTE_NO_COINCIDE"


def test_un_voucher_no_respalda_dos_pagos_y_al_tercer_rechazo_se_bloquea(
    cliente: TestClient, asistente: TestClient, gerente: TestClient, equipo: Equipo
) -> None:
    primera = deuda_de(gerente, 5)
    dobles(cliente).revisor.datos = replace(LEIDO, periodo="2026-10")
    segunda = deuda_de(gerente, 6)
    voucher(asistente)
    usado = comprobante(asistente, primera["id"], 108)
    assert pagar(asistente, primera["id"], usado["id"]).status_code == 201

    # El mismo archivo para otra deuda.
    mismo_archivo = comprobante(asistente, segunda["id"], 108)
    assert mismo_archivo["estado"] == "repetido"
    # Otra foto de la misma operación.
    misma_operacion = comprobante(asistente, segunda["id"], 109)
    assert misma_operacion["estado"] == "repetido"
    assert misma_operacion["registro_bloqueado"] is False
    # Un voucher borroso no cuenta como intento.
    dobles(cliente).lector.texto = "~~ ::"
    assert comprobante(asistente, segunda["id"], 110)["estado"] == "ilegible"
    # El tercero que no corresponde: paga otro suministro.
    voucher(asistente, codigo_pago="99990000", numero_operacion="0458777")
    tercero = comprobante(asistente, segunda["id"], 111)
    assert (tercero["estado"], tercero["registro_bloqueado"]) == ("rechazado", True)

    bloqueada = subir(asistente, segunda["id"], 112)
    assert (bloqueada.status_code, bloqueada.json()["code"]) == (403, "REGISTRO_PAGOS_BLOQUEADO")
    assert asistente.get(f"{PAGOS}/por-pagar").json()["registro_bloqueado"] is True
    assert [n["tipo"] for n in notificaciones(gerente)].count("REGISTRO_PAGOS_BLOQUEADO") == 1
    [bloqueo] = gerente.get("/api/v1/registro-pagos/bloqueos").json()
    assert bloqueo["asistente_id"] == str(equipo.asistente.id)
    # Ver y levantar el bloqueo es del gerente.
    ajeno = asistente.get("/api/v1/registro-pagos/bloqueos")
    assert (ajeno.status_code, ajeno.json()["code"]) == (403, "SIN_PERMISO")
    levantar = f"/api/v1/registro-pagos/bloqueos/{equipo.asistente.id}/levantamiento"
    assert gerente.post(levantar).status_code == 204
    assert "REGISTRO_PAGOS_DESBLOQUEADO" in [n["tipo"] for n in notificaciones(asistente)]
    voucher(asistente, numero_operacion="0458299")
    assert subir(asistente, segunda["id"], 113).status_code == 202


def test_una_deuda_vencida_pagada_con_mas_es_posible_mora_sin_castigo(
    asistente: TestClient, gerente: TestClient
) -> None:
    vencio = (hoy() - timedelta(days=11)).isoformat()
    deuda = deuda_de(gerente, 7, cuotas=[{"vence_el": vencio, "importe": "182.40"}])
    for semilla in (114, 115, 116):
        voucher(asistente, importe=Decimal("190.20"), numero_operacion=f"04582{semilla}")
        leido = comprobante(asistente, deuda["id"], semilla)
        assert leido["estado"] == "rechazado"
        assert [s["codigo"] for s in leido["senales"]] == ["POSIBLE_MORA"]
    # Tres posibles moras no bloquean: no son comprobantes que no correspondan.
    assert asistente.get(f"{PAGOS}/por-pagar").json()["registro_bloqueado"] is False


def test_solo_se_pagan_las_cuotas_registradas_y_con_sus_datos(
    asistente: TestClient, gerente: TestClient
) -> None:
    # Supera el límite del gerente: espera su autorización.
    assert gerente.post("/api/v1/reglas/limite", json={"limite_importe": "100.00"}).is_success
    por_autorizar = deuda_de(asistente, 8)
    assert por_autorizar["estado"] == "por_autorizar"
    respuesta = subir(asistente, por_autorizar["id"], 117)
    assert (respuesta.status_code, respuesta.json()["code"]) == (409, "DEUDA_POR_AUTORIZAR")
    sin_datos = asistente.post(COMPROBANTES, files={"archivo": ("v.png", imagen(118), "image/png")})
    assert (sin_datos.status_code, sin_datos.json()["code"]) == (422, "CAMPOS_OBLIGATORIOS")
    assert set(sin_datos.json()["fields"]) == {"deuda_id", "cuota"}
    vacio = pagar(asistente, por_autorizar["id"])
    assert (vacio.status_code, set(vacio.json()["fields"])) == (422, {"comprobantes"})


def test_un_comprobante_lo_usan_solo_quien_lo_subio_y_en_su_espacio(
    cliente: TestClient, asistente: TestClient, gerente: TestClient, equipo: Equipo
) -> None:
    deuda = deuda_de(gerente, 9)
    voucher(asistente)
    leido = comprobante(asistente, deuda["id"], 119)
    rosa = sesion(cliente, equipo.otra_asistente)
    otro = sesion(cliente, equipo.otro_gerente)

    ajeno = pagar(rosa, deuda["id"], leido["id"])
    assert (ajeno.status_code, ajeno.json()["code"]) == (404, "COMPROBANTE_NO_ENCONTRADO")
    assert rosa.get(f"{COMPROBANTES}/{leido['id']}").status_code == 404
    assert otro.get(f"{COMPROBANTES}/{leido['id']}/contenido").status_code == 404
    assert gerente.get(f"{COMPROBANTES}/{leido['id']}/contenido").status_code == 200
    otro_espacio = otro.get(f"{PAGOS}/por-pagar").json()["cuotas"]
    assert otro_espacio == []


def test_dos_registros_simultaneos_de_la_misma_cuota_crean_un_solo_pago(
    asistente: TestClient, gerente: TestClient
) -> None:
    deuda = deuda_de(gerente, 10)
    voucher(asistente, numero_operacion="1001")
    uno = comprobante(asistente, deuda["id"], 120)
    voucher(asistente, numero_operacion="1002")
    otro = comprobante(asistente, deuda["id"], 121)

    with ThreadPoolExecutor(max_workers=2) as hilos:
        respuestas = list(hilos.map(lambda c: pagar(asistente, deuda["id"], c["id"]), (uno, otro)))

    assert sorted(r.status_code for r in respuestas) == [201, 409]
    assert len(gerente.get(PAGOS).json()) == 1


def registrado(asistente: TestClient, gerente: TestClient, semilla: int) -> tuple[dict, dict]:
    """Una deuda del gerente que la asistente pagó con un voucher: el pago espera verificación."""
    deuda = deuda_de(gerente, semilla)
    voucher(asistente, numero_operacion=f"07{semilla:06d}")
    leido = comprobante(asistente, deuda["id"], 200 + semilla)
    pago = pagar(asistente, deuda["id"], leido["id"])
    assert pago.status_code == 201, pago.json()
    return deuda, pago.json()


def test_el_gerente_ve_los_comprobantes_y_confirma_el_pago(
    asistente: TestClient, gerente: TestClient
) -> None:
    deuda, pago = registrado(asistente, gerente, 11)
    detalle = gerente.get(f"{PAGOS}/{pago['id']}").json()
    [voucher_leido] = detalle["detalle_comprobantes"]
    assert voucher_leido["lectura"]["numero_operacion"] == "07000011"
    assert detalle["confianza"] is not None

    confirmado = gerente.post(f"{PAGOS}/{pago['id']}/confirmacion")

    assert (confirmado.status_code, confirmado.json()["estado"]) == (200, "confirmado")
    assert "PAGO_CONFIRMADO" in [n["tipo"] for n in notificaciones(asistente)]
    cuota = gerente.get(f"{DEUDAS}/{deuda['id']}").json()["cuotas"][0]
    assert cuota["pago"] == "confirmado"
    otra_vez = gerente.post(f"{PAGOS}/{pago['id']}/devolucion", json={"motivo": "No"})
    assert (otra_vez.status_code, otra_vez.json()["code"]) == (409, "ESTADO_NO_PERMITE")


def test_un_pago_devuelto_vuelve_la_cuota_por_pagar_y_su_voucher_no_se_reutiliza(
    asistente: TestClient, gerente: TestClient
) -> None:
    deuda, pago = registrado(asistente, gerente, 12)
    sin_motivo = gerente.post(f"{PAGOS}/{pago['id']}/devolucion", json={"motivo": "  "})
    assert (sin_motivo.status_code, set(sin_motivo.json()["fields"])) == (422, {"motivo"})

    devuelto = gerente.post(
        f"{PAGOS}/{pago['id']}/devolucion", json={"motivo": "El voucher es de otro mes."}
    )

    assert devuelto.json()["estado"] == "devuelto"
    [aviso] = [n for n in notificaciones(asistente) if n["tipo"] == "PAGO_DEVUELTO"]
    assert "El voucher es de otro mes." in aviso["cuerpo"]
    [cuota] = asistente.get(f"{PAGOS}/por-pagar").json()["cuotas"]
    assert (cuota["deuda_id"], cuota["devuelto_por"]) == (deuda["id"], "El voucher es de otro mes.")
    # El mismo voucher no respalda otro pago, ni siquiera de la misma cuota.
    voucher(asistente, numero_operacion="07000012")
    assert comprobante(asistente, deuda["id"], 212)["estado"] == "repetido"


def test_solo_el_gerente_de_su_espacio_decide_un_pago(
    cliente: TestClient, asistente: TestClient, gerente: TestClient, equipo: Equipo
) -> None:
    _, pago = registrado(asistente, gerente, 13)
    otro = sesion(cliente, equipo.otro_gerente)

    propio = asistente.post(f"{PAGOS}/{pago['id']}/confirmacion")
    assert (propio.status_code, propio.json()["code"]) == (403, "SIN_PERMISO")
    ajeno = otro.post(f"{PAGOS}/{pago['id']}/confirmacion")
    assert (ajeno.status_code, ajeno.json()["code"]) == (404, "PAGO_NO_ENCONTRADO")
    assert otro.get(f"{PAGOS}/{pago['id']}").status_code == 404
