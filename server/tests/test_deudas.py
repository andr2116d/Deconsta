from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from tests.conftest import Equipo, consultar
from tests.dobles import imagen
from tests.test_categorias import sesion
from tests.test_contrasena_y_desbloqueo import base_de
from tests.test_documentos import LEIDO, dobles, subir

DEUDAS = "/api/v1/deudas"
VENCE = (date.today() + timedelta(days=7)).isoformat()


@pytest.fixture
def gerente(cliente: TestClient, equipo: Equipo) -> TestClient:
    dobles(cliente).revisor.datos = LEIDO
    return sesion(cliente, equipo.gerente)


@pytest.fixture
def asistente(cliente: TestClient, equipo: Equipo) -> TestClient:
    dobles(cliente).revisor.datos = LEIDO
    return sesion(cliente, equipo.asistente)


def registrar(cliente: TestClient, documento_id: str, **cambios: Any) -> httpx.Response:
    cuerpo = {
        "documento_id": documento_id,
        "concepto": "Luz de la casa",
        "lugar_pago": "agente",
        "cuotas": [{"vence_el": VENCE, "importe": "182.40"}],
        "titular_nombre": "Valentina Ramos Díaz",
        "codigo_pago": "54871236",
        **cambios,
    }
    return cliente.post(DEUDAS, json=cuerpo)


def nueva(cliente: TestClient, semilla: int, **cambios: Any) -> dict:
    documento = subir(cliente, imagen(semilla))
    respuesta = registrar(cliente, documento["id"], **cambios)
    assert respuesta.status_code == 201, respuesta.json()
    return respuesta.json()


def notificaciones(cliente: TestClient) -> list[dict]:
    return cliente.get("/api/v1/notificaciones").json()["notificaciones"]


def test_el_formulario_con_campos_obligatorios_vacios_dice_cuales_faltan(
    asistente: TestClient,
) -> None:
    documento = subir(asistente, imagen(1))
    respuesta = registrar(asistente, documento["id"], concepto=" ", lugar_pago=None, cuotas=[])

    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "CAMPOS_OBLIGATORIOS"
    assert set(respuesta.json()["fields"]) == {"concepto"}
    # Con el concepto, el dominio marca los demás.
    respuesta = registrar(asistente, documento["id"], lugar_pago=None, cuotas=[])
    assert respuesta.json()["code"] == "DATOS_INVALIDOS"
    assert set(respuesta.json()["fields"]) == {"lugar_pago", "cuotas"}


def test_lo_que_registra_la_asistente_se_paga_y_se_notifica_al_gerente(
    cliente: TestClient, asistente: TestClient, gerente: TestClient
) -> None:
    registro = nueva(asistente, 2)
    deuda = registro["deuda"]

    assert deuda["estado"] == "registrada"
    assert deuda["revision_pendiente"] is True
    assert deuda["registrada_por"]["nombre"] == "Lucía Vega"
    avisos = notificaciones(gerente)
    assert [(n["tipo"], n["deuda_id"]) for n in avisos] == [("DEUDA_REGISTRADA", deuda["id"])]
    assert [a.tipo for a in dobles(cliente).publicador.avisos] == ["DEUDA_REGISTRADA"]
    # Queda en sus pendientes hasta darle el visto bueno, que no se repite.
    assert [d["id"] for d in gerente.get(DEUDAS, params={"pendientes": True}).json()] == [
        deuda["id"]
    ]
    assert gerente.post(f"{DEUDAS}/{deuda['id']}/revision").json()["revision_pendiente"] is False
    otra_vez = gerente.post(f"{DEUDAS}/{deuda['id']}/revision")
    assert (otra_vez.status_code, otra_vez.json()["code"]) == (409, "ESTADO_NO_PERMITE")
    assert gerente.get(DEUDAS, params={"pendientes": True}).json() == []


def test_sobre_el_limite_espera_al_gerente_y_su_decision_se_notifica(
    cliente: TestClient, asistente: TestClient, gerente: TestClient
) -> None:
    gerente.post("/api/v1/reglas/limite", json={"limite_importe": "100.00"})
    deuda = nueva(asistente, 3)["deuda"]

    assert deuda["estado"] == "por_autorizar"
    assert deuda["motivos"] == ["IMPORTE_SOBRE_LIMITE"]
    assert notificaciones(gerente)[0]["tipo"] == "DEUDA_POR_AUTORIZAR"
    # La asistente no decide.
    assert asistente.post(f"{DEUDAS}/{deuda['id']}/autorizacion").status_code == 403

    autorizada = gerente.post(f"{DEUDAS}/{deuda['id']}/autorizacion").json()
    assert autorizada["estado"] == "registrada"
    assert notificaciones(asistente)[0]["tipo"] == "DEUDA_AUTORIZADA"
    rechazo = gerente.post(f"{DEUDAS}/{deuda['id']}/rechazo", json={"motivo": "No es mía"})
    assert (rechazo.status_code, rechazo.json()["code"]) == (409, "ESTADO_NO_PERMITE")
    auditoria = consultar(
        base_de(cliente),
        "SELECT accion FROM auditoria WHERE detalle->>'deuda_id' = %s ORDER BY id",
        deuda["id"],
    )
    assert auditoria == [("DEUDA_REGISTRADA",), ("DEUDA_AUTORIZADA",)]


def test_rechazar_o_anular_exige_un_motivo_que_ve_la_asistente(
    asistente: TestClient, gerente: TestClient
) -> None:
    deuda = nueva(asistente, 4)["deuda"]

    sin_motivo = gerente.post(f"{DEUDAS}/{deuda['id']}/anulacion", json={"motivo": "  "})
    assert sin_motivo.status_code == 422
    assert set(sin_motivo.json()["fields"]) == {"motivo"}
    anulada = gerente.post(f"{DEUDAS}/{deuda['id']}/anulacion", json={"motivo": "Ya se pagó"})
    assert anulada.json()["estado"] == "anulada"
    aviso = notificaciones(asistente)[0]
    assert aviso["tipo"] == "DEUDA_ANULADA"
    assert aviso["cuerpo"].endswith("Motivo: Ya se pagó")


def test_lo_que_registra_el_gerente_no_espera_ni_se_notifica(
    gerente: TestClient,
) -> None:
    gerente.post("/api/v1/reglas/limite", json={"limite_importe": "100.00"})
    registro = nueva(gerente, 5, titular_nombre="Otra Persona")
    assert registro["deuda"]["estado"] == "registrada"
    assert registro["deuda"]["revision_pendiente"] is False
    assert notificaciones(gerente) == []


def test_el_mismo_documento_no_respalda_dos_deudas_y_al_tercer_intento_se_bloquea(
    cliente: TestClient, asistente: TestClient, gerente: TestClient, equipo: Equipo
) -> None:
    contenido = imagen(6)
    documento = subir(asistente, contenido)
    deuda = registrar(asistente, documento["id"]).json()["deuda"]

    for intento in range(1, 4):
        repetido = asistente.post("/api/v1/documentos", files={"archivo": ("r.png", contenido)})
        assert repetido.status_code == 409
        cuerpo = repetido.json()
        assert cuerpo["code"] == "DOCUMENTO_YA_REGISTRADO"
        assert cuerpo["existing_debt"]["concepto"] == "Luz de la casa"
        assert cuerpo["registration_blocked"] is (intento == 3)

    bloqueos = [n for n in notificaciones(gerente) if n["tipo"] == "REGISTRO_BLOQUEADO"]
    assert len(bloqueos) == 1
    assert bloqueos[0]["cuenta_id"] == str(equipo.asistente.id)
    bloqueada = asistente.post("/api/v1/documentos", files={"archivo": ("n.png", imagen(7))})
    assert (bloqueada.status_code, bloqueada.json()["code"]) == (403, "REGISTRO_DEUDAS_BLOQUEADO")
    # Su cuenta sigue activa: solo no registra deudas.
    assert asistente.get(f"{DEUDAS}/{deuda['id']}").status_code == 200

    assert gerente.get("/api/v1/registro-deudas/bloqueos").json()[0]["asistente_id"] == str(
        equipo.asistente.id
    )
    levantar = f"/api/v1/registro-deudas/bloqueos/{equipo.asistente.id}/levantamiento"
    assert gerente.post(levantar).status_code == 204
    assert notificaciones(asistente)[0]["tipo"] == "REGISTRO_DESBLOQUEADO"
    # Los intentos anteriores al levantamiento ya no cuentan.
    repetido = asistente.post("/api/v1/documentos", files={"archivo": ("r.png", contenido)})
    assert repetido.json()["registration_blocked"] is False


def test_al_gerente_nunca_se_le_bloquea_por_repetir_un_documento(
    cliente: TestClient, gerente: TestClient
) -> None:
    contenido = imagen(8)
    registrar(gerente, subir(gerente, contenido)["id"])
    for _ in range(4):
        repetido = gerente.post("/api/v1/documentos", files={"archivo": ("r.png", contenido)})
        assert repetido.json()["registration_blocked"] is False
    # Sigue probando hasta dar con el recibo nuevo, el del mes siguiente.
    dobles(cliente).revisor.datos = replace(LEIDO, periodo="2026-10")
    assert subir(gerente, imagen(9))["estado"] == "listo"


@pytest.mark.parametrize(
    ("preparar", "codigo"),
    [
        ("ilegible", "DOCUMENTO_ILEGIBLE"),
        ("alterado", "DOCUMENTO_RECHAZADO"),
        ("pausada", "DOCUMENTO_EN_ANALISIS"),
    ],
)
def test_solo_un_documento_listo_respalda_una_deuda(
    cliente: TestClient, asistente: TestClient, preparar: str, codigo: str
) -> None:
    doble = dobles(cliente)
    if preparar == "ilegible":
        doble.lector.texto = ""
    elif preparar == "alterado":
        doble.revisor.veredicto = "alterado"
    else:
        doble.cola.pausada = True
    respuesta = asistente.post("/api/v1/documentos", files={"archivo": ("r.png", imagen(10))})
    registro = registrar(asistente, respuesta.json()["id"])
    assert (registro.status_code, registro.json()["code"]) == (409, codigo)


def test_solo_quien_subio_el_documento_lo_registra(
    asistente: TestClient, gerente: TestClient
) -> None:
    documento = subir(gerente, imagen(11))
    respuesta = registrar(asistente, documento["id"])
    assert (respuesta.status_code, respuesta.json()["code"]) == (404, "DOCUMENTO_NO_ENCONTRADO")


def test_dos_registros_simultaneos_del_mismo_documento_crean_una_sola_deuda(
    cliente: TestClient, asistente: TestClient
) -> None:
    documento = subir(asistente, imagen(12))
    with ThreadPoolExecutor(max_workers=4) as hilos:
        estados = sorted(
            r.status_code
            for r in hilos.map(lambda _: registrar(asistente, documento["id"]), range(4))
        )
    assert estados == [201, 409, 409, 409]
    assert consultar(base_de(cliente), "SELECT count(*) FROM deuda") == [(1,)]


def test_un_cronograma_registra_sus_cuotas_con_importes_distintos(
    asistente: TestClient, gerente: TestClient
) -> None:
    inicio = date.today() + timedelta(days=10)
    cuotas = [
        {"vence_el": (inicio + timedelta(days=30 * i)).isoformat(), "importe": importe}
        for i, importe in enumerate(["350.00", "350.00", "362.75"])
    ]
    deuda = nueva(asistente, 13, cuotas=cuotas)["deuda"]

    assert deuda["importe"] == "1062.75"
    assert [c["importe"] for c in deuda["cuotas"]] == ["350.00", "350.00", "362.75"]
    detalle = gerente.get(f"{DEUDAS}/{deuda['id']}").json()
    assert detalle["documento"]["propuesta"]["importe"] == "182.40"
    assert "importe" in detalle["campos_corregidos"]


def test_la_categoria_debe_ser_una_activa_del_espacio(
    cliente: TestClient, asistente: TestClient, equipo: Equipo
) -> None:
    otro = sesion(cliente, equipo.otro_gerente)
    ajena = otro.post("/api/v1/categorias", json={"nombre": "Luz"}).json()
    documento = subir(asistente, imagen(14))
    respuesta = registrar(asistente, documento["id"], categoria_id=ajena["id"])
    assert (respuesta.status_code, respuesta.json()["code"]) == (422, "CATEGORIA_NO_DISPONIBLE")


def test_una_deuda_de_otro_espacio_no_existe_para_este(
    cliente: TestClient, asistente: TestClient, equipo: Equipo
) -> None:
    deuda = nueva(asistente, 15)["deuda"]
    otro = sesion(cliente, equipo.otro_gerente)
    for respuesta in (
        otro.get(f"{DEUDAS}/{deuda['id']}"),
        otro.post(f"{DEUDAS}/{deuda['id']}/anulacion", json={"motivo": "No"}),
    ):
        assert (respuesta.status_code, respuesta.json()["code"]) == (404, "DEUDA_NO_ENCONTRADA")


def test_cada_cuenta_marca_solo_sus_notificaciones(
    cliente: TestClient, asistente: TestClient, gerente: TestClient
) -> None:
    nueva(asistente, 16)
    aviso = notificaciones(gerente)[0]

    ajena = asistente.post(f"/api/v1/notificaciones/{aviso['id']}/lectura")
    assert (ajena.status_code, ajena.json()["code"]) == (404, "NOTIFICACION_NO_ENCONTRADA")
    assert gerente.post(f"/api/v1/notificaciones/{aviso['id']}/lectura").status_code == 204
    bandeja = gerente.get("/api/v1/notificaciones").json()
    assert (bandeja["no_leidas"], bandeja["notificaciones"][0]["leida"]) == (0, True)


def test_el_flujo_de_avisos_exige_sesion(cliente: TestClient) -> None:
    respuesta = cliente.get("/api/v1/notificaciones/flujo")
    assert (respuesta.status_code, respuesta.json()["code"]) == (401, "NO_AUTENTICADO")
