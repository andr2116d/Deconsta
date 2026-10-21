from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from tests.conftest import Equipo, FabricaCliente, consultar, habilitar
from tests.test_contrasena_y_desbloqueo import base_de, ingresar

CATEGORIAS = "/api/v1/categorias"
AGUA = {
    "nombre": "Agua",
    "descripcion": "Recibos de Sedapal del local y de la casa.",
    "color": "azul",
    "icono": "agua",
}


def sesion(cliente: TestClient, cuenta: object) -> TestClient:
    """Cliente nuevo de la misma app con la sesión de la cuenta, ya habilitada."""
    nuevo = TestClient(cliente.app)
    habilitar(base_de(cliente), cuenta.id)  # type: ignore[attr-defined]
    ingresar(nuevo, cuenta.usuario, cuenta.contrasena)  # type: ignore[attr-defined]
    return nuevo


@pytest.fixture
def gerente(cliente: TestClient, equipo: Equipo) -> TestClient:
    return sesion(cliente, equipo.gerente)


def crear(cliente: TestClient, **cambios: object) -> dict:
    respuesta = cliente.post(CATEGORIAS, json={**AGUA, **cambios})
    assert respuesta.status_code == 201, respuesta.json()
    return respuesta.json()


def test_el_gerente_crea_una_categoria_y_queda_auditada(gerente: TestClient) -> None:
    creada = crear(gerente, nombre="  Agua   potable ")

    assert creada["nombre"] == "Agua potable"
    assert creada["color"] == "azul"
    assert creada["icono"] == "agua"
    assert creada["archivada"] is False
    assert [c["nombre"] for c in gerente.get(CATEGORIAS).json()] == ["Agua potable"]
    auditoria = consultar(
        base_de(gerente),
        "SELECT actor_id IS NOT NULL, detalle FROM auditoria WHERE accion = 'CATEGORIA_CREADA'",
    )
    assert auditoria == [(True, {"categoria_id": creada["id"], "nombre": "Agua potable"})]


def test_sin_color_ni_icono_asigna_unos_por_defecto(gerente: TestClient) -> None:
    primera = crear(gerente, nombre="Luz", color=None, icono=None)
    segunda = crear(gerente, nombre="Gas", color=None, icono=None)

    assert primera["icono"] == "etiqueta"
    assert primera["color"] != segunda["color"]


def test_rechaza_el_formulario_con_el_nombre_vacio(gerente: TestClient) -> None:
    for cuerpo in ({}, {"nombre": "   ", "color": "azul"}):
        respuesta = gerente.post(CATEGORIAS, json=cuerpo)
        assert respuesta.status_code == 422
        assert respuesta.json()["code"] == "CAMPOS_OBLIGATORIOS"
        assert respuesta.json()["fields"] == {"nombre": "Escribe el nombre de la categoría."}
    assert gerente.get(CATEGORIAS).json() == []


def test_rechaza_datos_invalidos_con_el_detalle_de_cada_campo(gerente: TestClient) -> None:
    respuesta = gerente.post(
        CATEGORIAS, json={"nombre": "<script>", "color": "fucsia", "icono": "cohete"}
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "DATOS_INVALIDOS"
    assert set(respuesta.json()["fields"]) == {"nombre", "color", "icono"}


def test_no_repite_un_nombre_aunque_cambien_mayusculas_o_tildes(gerente: TestClient) -> None:
    crear(gerente, nombre="Teléfono")

    respuesta = gerente.post(CATEGORIAS, json={**AGUA, "nombre": "TELEFONO"})

    assert respuesta.status_code == 409
    assert respuesta.json()["code"] == "CATEGORIA_DUPLICADA"
    assert respuesta.json()["fields"]["nombre"] == "Ya tienes una categoría llamada «Teléfono»."
    assert respuesta.json()["existing_category"]["archivada"] is False


def test_una_categoria_archivada_se_reactiva_en_lugar_de_repetirse(gerente: TestClient) -> None:
    luz = crear(gerente, nombre="Luz")
    archivada = gerente.post(f"{CATEGORIAS}/{luz['id']}/archivado", json={"motivo": "Ya no"})
    assert archivada.json()["archivada"] is True
    assert gerente.get(CATEGORIAS).json() == []

    repetida = gerente.post(CATEGORIAS, json={**AGUA, "nombre": "luz"})
    assert repetida.status_code == 409
    assert repetida.json()["existing_category"] == {"id": luz["id"], "archivada": True}

    # Archivada no se edita; reactivada vuelve a la lista.
    edicion = gerente.post(f"{CATEGORIAS}/{luz['id']}/edicion", json={"nombre": "Electricidad"})
    assert edicion.json()["code"] == "CATEGORIA_ARCHIVADA"
    assert gerente.post(f"{CATEGORIAS}/{luz['id']}/reactivacion").status_code == 200
    assert [c["nombre"] for c in gerente.get(CATEGORIAS).json()] == ["Luz"]
    acciones = consultar(
        base_de(gerente),
        "SELECT accion, motivo FROM auditoria WHERE accion LIKE 'CATEGORIA_%' ORDER BY id",
    )
    assert acciones == [
        ("CATEGORIA_CREADA", None),
        ("CATEGORIA_ARCHIVADA", "Ya no"),
        ("CATEGORIA_REACTIVADA", None),
    ]


def test_edita_una_categoria_y_avisa_si_no_hay_cambios(gerente: TestClient) -> None:
    agua = crear(gerente)
    ruta = f"{CATEGORIAS}/{agua['id']}/edicion"

    editada = gerente.post(ruta, json={"nombre": "Agua y desagüe", "descripcion": None})
    assert editada.status_code == 200
    assert editada.json()["nombre"] == "Agua y desagüe"
    # Sin color ni ícono conserva los actuales.
    assert (editada.json()["color"], editada.json()["icono"]) == ("azul", "agua")

    repetida = gerente.post(ruta, json={"nombre": " Agua y  desagüe "})
    assert repetida.status_code == 422
    assert repetida.json()["code"] == "SIN_CAMBIOS"


def test_solo_el_gerente_administra_y_cada_equipo_ve_lo_suyo(
    cliente: TestClient, gerente: TestClient, equipo: Equipo
) -> None:
    agua = crear(gerente)
    archivada = crear(gerente, nombre="Seguros")
    gerente.post(f"{CATEGORIAS}/{archivada['id']}/archivado")

    # La asistente del equipo consulta solo las activas, pero no administra.
    asistente = sesion(cliente, equipo.asistente)
    vistas = asistente.get(CATEGORIAS, params={"archivadas": True}).json()
    assert [c["nombre"] for c in vistas] == ["Agua"]
    assert asistente.post(CATEGORIAS, json=AGUA).json()["code"] == "SIN_PERMISO"
    assert asistente.post(f"{CATEGORIAS}/{agua['id']}/archivado").status_code == 403

    # Otro gerente no ve ni toca las categorías ajenas.
    otro = sesion(cliente, equipo.otro_gerente)
    assert otro.get(CATEGORIAS).json() == []
    ajena = otro.post(f"{CATEGORIAS}/{agua['id']}/edicion", json={"nombre": "Mía"})
    assert ajena.status_code == 404
    assert ajena.json()["code"] == "CATEGORIA_NO_ENCONTRADA"
    assert crear(otro)["nombre"] == "Agua"

    # Sin sesión no hay nada.
    assert TestClient(cliente.app).get(CATEGORIAS).status_code == 401


def test_limita_las_categorias_activas_del_espacio(
    gerente: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.categorias.aplicacion.categorias.MAXIMO_CATEGORIAS_ACTIVAS", 2)
    luz = crear(gerente, nombre="Luz")
    crear(gerente, nombre="Gas")

    respuesta = gerente.post(CATEGORIAS, json=AGUA)
    assert respuesta.status_code == 409
    assert respuesta.json()["code"] == "LIMITE_CATEGORIAS"

    # Archivar libera un lugar.
    gerente.post(f"{CATEGORIAS}/{luz['id']}/archivado")
    crear(gerente)


def test_limita_los_intentos_de_cada_gerente(crear_cliente: FabricaCliente, equipo: Equipo) -> None:
    gerente = sesion(crear_cliente(limite_gestion_categorias=2), equipo.gerente)
    crear(gerente, nombre="Luz")
    crear(gerente, nombre="Gas")

    respuesta = gerente.post(CATEGORIAS, json=AGUA)

    assert respuesta.status_code == 429
    assert respuesta.json()["code"] == "DEMASIADAS_SOLICITUDES"
    assert int(respuesta.headers["Retry-After"]) > 0


def test_solicitudes_simultaneas_crean_una_sola_categoria(gerente: TestClient) -> None:
    with ThreadPoolExecutor(max_workers=6) as hilos:
        estados = list(
            hilos.map(lambda _: gerente.post(CATEGORIAS, json=AGUA).status_code, range(6))
        )

    assert sorted(estados) == [201] + [409] * 5
    assert len(gerente.get(CATEGORIAS).json()) == 1
