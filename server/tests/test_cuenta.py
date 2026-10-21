import psycopg
import pytest
from fastapi.testclient import TestClient

from tests.conftest import Equipo, consultar, habilitar
from tests.test_contrasena_y_desbloqueo import base_de, ingresar

CUENTA = "/api/v1/cuenta"
DATOS = "/api/v1/cuenta/datos"
USUARIO = "/api/v1/cuenta/nombre-usuario"


@pytest.fixture
def gerente(cliente: TestClient, equipo: Equipo) -> dict:
    """Sesión del gerente habilitado; devuelve su ficha inicial."""
    habilitar(base_de(cliente), equipo.gerente.id, equipo.asistente.id)
    ingresar(cliente, equipo.gerente.usuario, equipo.gerente.contrasena)
    respuesta = cliente.get(CUENTA)
    assert respuesta.status_code == 200
    return respuesta.json()


def editable(cuenta: dict, **cambios: object) -> dict:
    campos = ("nombres", "apellidos", "correo", "telefono", "tipo_documento", "numero_documento")
    return {**{c: cuenta[c] for c in campos}, "nombre_recibos": cuenta["nombre_recibos"], **cambios}


def test_muestra_los_datos_descifrados_y_el_cupo_de_cambios(gerente: dict) -> None:
    assert gerente["nombres"] == "Valentina"
    assert gerente["apellidos"] == "Ramos"
    assert gerente["numero_documento"] == "45678912"
    assert gerente["cargo"] is None
    assert gerente["nombre_recibos"] is None
    cupo = gerente["cambios_nombre_usuario"]
    assert (cupo["maximo"], cupo["usados"], cupo["restantes"]) == (3, 0, 3)
    assert cupo["renueva_en"].endswith("-05:00")


def test_consultar_pide_sesion_y_actualizar_la_incorporacion_completa(
    cliente: TestClient, equipo: Equipo
) -> None:
    assert cliente.get(CUENTA).status_code == 401
    ingresar(cliente, equipo.gerente.usuario, equipo.gerente.contrasena)
    # Sus propios datos se consultan también durante el primer ingreso.
    cuenta = cliente.get(CUENTA).json()
    assert cuenta["nombres"] == "Valentina"
    respuesta = cliente.post(DATOS, json=editable(cuenta, telefono="912345678"))
    assert respuesta.json()["code"] == "INCORPORACION_PENDIENTE"


def test_actualiza_los_datos_y_el_nombre_de_la_sesion(
    cliente: TestClient, equipo: Equipo, gerente: dict
) -> None:
    respuesta = cliente.post(
        DATOS,
        json=editable(gerente, nombres="Valentina  Sofía", nombre_recibos="Ramos, Valentina"),
    )

    assert respuesta.status_code == 200, respuesta.json()
    assert respuesta.json()["nombres"] == "Valentina Sofía"
    assert cliente.get("/api/v1/auth/me").json()["usuario"]["nombres"] == "Valentina Sofía"
    assert cliente.get(CUENTA).json()["nombre_recibos"] == "Ramos, Valentina"
    # El valor se guarda cifrado y la auditoría solo nombra los campos.
    filas = consultar(
        base_de(cliente),
        "SELECT nombre_recibos_cifrado, (SELECT detalle FROM auditoria"
        " WHERE accion = 'DATOS_PERSONALES_ACTUALIZADOS') FROM usuario WHERE id = %s",
        equipo.gerente.id,
    )
    cifrado, detalle = filas[0]
    assert b"Ramos" not in bytes(cifrado)
    assert detalle == {"campos": ["nombres", "nombre_recibos"]}


def test_rechaza_un_envio_sin_cambios_reales(cliente: TestClient, gerente: dict) -> None:
    respuesta = cliente.post(DATOS, json=editable(gerente, nombres=" Valentina "))
    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "SIN_CAMBIOS"


def test_cambiar_el_correo_pide_la_contrasena_actual(
    cliente: TestClient, equipo: Equipo, gerente: dict
) -> None:
    nuevo = editable(gerente, correo="valentina.nueva@ejemplo.pe")

    assert cliente.post(DATOS, json=nuevo).json()["code"] == "CONTRASENA_REQUERIDA"
    incorrecta = cliente.post(DATOS, json={**nuevo, "contrasena_actual": "Incorrecta123"})
    assert incorrecta.status_code == 400
    assert cliente.get(CUENTA).json()["correo"] == gerente["correo"]

    correcta = cliente.post(DATOS, json={**nuevo, "contrasena_actual": equipo.gerente.contrasena})
    assert correcta.status_code == 200
    assert correcta.json()["correo"] == "valentina.nueva@ejemplo.pe"
    acciones = consultar(
        base_de(cliente),
        "SELECT accion FROM auditoria WHERE accion IN"
        " ('CONFIRMACION_CONTRASENA_FALLIDA', 'DATOS_PERSONALES_ACTUALIZADOS') ORDER BY id",
    )
    assert acciones == [("CONFIRMACION_CONTRASENA_FALLIDA",), ("DATOS_PERSONALES_ACTUALIZADOS",)]


def test_no_toma_el_correo_de_otra_cuenta(
    cliente: TestClient, equipo: Equipo, gerente: dict
) -> None:
    respuesta = cliente.post(
        DATOS,
        json=editable(
            gerente,
            correo="martín.40000001@ejemplo.pe",
            contrasena_actual=equipo.gerente.contrasena,
        ),
    )
    assert respuesta.status_code == 409
    assert "correo" in respuesta.json()["fields"]


def test_el_numero_de_documento_no_cambia(cliente: TestClient, gerente: dict) -> None:
    respuesta = cliente.post(DATOS, json=editable(gerente, numero_documento="45678913"))
    assert respuesta.json()["code"] == "DOCUMENTO_NO_MODIFICABLE"


def test_pasa_de_dni_a_carne_con_confirmacion_y_lo_audita(
    cliente: TestClient, equipo: Equipo, gerente: dict
) -> None:
    carne = editable(
        gerente,
        tipo_documento="ce",
        numero_documento="001234567",
        contrasena_actual=equipo.gerente.contrasena,
    )
    assert cliente.post(DATOS, json=carne).json()["code"] == "CAMBIO_DOCUMENTO_SIN_CONFIRMAR"

    respuesta = cliente.post(DATOS, json={**carne, "confirmar_cambio_documento": True})

    assert respuesta.status_code == 200
    assert respuesta.json()["tipo_documento"] == "ce"
    eventos = consultar(
        base_de(cliente), "SELECT detalle FROM auditoria WHERE accion = 'DOCUMENTO_CAMBIADO'"
    )
    assert eventos == [({"de": "dni", "a": "ce"},)]


def test_la_asistente_no_registra_nombre_en_recibos(cliente: TestClient, equipo: Equipo) -> None:
    habilitar(base_de(cliente), equipo.asistente.id)
    ingresar(cliente, equipo.asistente.usuario, equipo.asistente.contrasena)
    cuenta = cliente.get(CUENTA).json()

    respuesta = cliente.post(DATOS, json=editable(cuenta, nombre_recibos="Vega, Lucía"))

    assert respuesta.status_code == 403


def test_cambia_el_usuario_hasta_tres_veces_por_mes(
    cliente: TestClient, equipo: Equipo, gerente: dict
) -> None:
    contrasena = equipo.gerente.contrasena
    for numero in range(1, 4):
        respuesta = cliente.post(
            USUARIO,
            json={"nombre_usuario": f" Valentina.R{numero} ", "contrasena_actual": contrasena},
        )
        assert respuesta.status_code == 200, respuesta.json()
        assert respuesta.json()["nombre_usuario"] == f"valentina.r{numero}"
        assert respuesta.json()["cambios_nombre_usuario"]["restantes"] == 3 - numero

    cuarto = cliente.post(
        USUARIO, json={"nombre_usuario": "valentina.r4", "contrasena_actual": contrasena}
    )

    assert cuarto.status_code == 409
    assert cuarto.json()["code"] == "LIMITE_CAMBIOS_USUARIO"
    assert cuarto.json()["renews_at"].endswith("-05:00")
    # La sesión sigue abierta y el nuevo usuario sirve para ingresar.
    assert cliente.get("/api/v1/auth/me").json()["usuario"]["nombre_usuario"] == "valentina.r3"
    ingresar(TestClient(cliente.app), "valentina.r3", contrasena)


def test_los_cambios_de_meses_anteriores_no_cuentan(
    cliente: TestClient, equipo: Equipo, gerente: dict
) -> None:
    consultar(
        base_de(cliente),
        "INSERT INTO cambio_nombre_usuario (usuario_id, anterior, nuevo, cambiado_en)"
        " SELECT %s, 'a' || n, 'b' || n, date_trunc('month', now()) - interval '1 day'"
        " FROM generate_series(1, 3) n",
        equipo.gerente.id,
    )
    assert cliente.get(CUENTA).json()["cambios_nombre_usuario"]["restantes"] == 3


def test_el_cambio_de_usuario_pide_la_contrasena_antes_de_revelar_si_existe(
    cliente: TestClient, equipo: Equipo, gerente: dict
) -> None:
    ajeno = {"nombre_usuario": equipo.otro_gerente.usuario}

    incorrecta = cliente.post(USUARIO, json={**ajeno, "contrasena_actual": "Incorrecta123"})
    ocupado = cliente.post(USUARIO, json={**ajeno, "contrasena_actual": equipo.gerente.contrasena})
    mismo = cliente.post(
        USUARIO,
        json={"nombre_usuario": equipo.gerente.usuario, "contrasena_actual": "x"},
    )

    assert incorrecta.json()["code"] == "CONTRASENA_ACTUAL_INCORRECTA"
    assert ocupado.status_code == 409
    assert ocupado.json()["fields"]["nombre_usuario"] == "Ese usuario ya está en uso."
    assert mismo.json()["code"] == "SIN_CAMBIOS"
    assert cliente.get(CUENTA).json()["cambios_nombre_usuario"]["usados"] == 0


def test_el_historial_de_cambios_de_usuario_no_se_modifica(
    cliente: TestClient, equipo: Equipo, gerente: dict
) -> None:
    cliente.post(
        USUARIO,
        json={"nombre_usuario": "valentina.r", "contrasena_actual": equipo.gerente.contrasena},
    )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        consultar(base_de(cliente), "DELETE FROM cambio_nombre_usuario")


def test_limita_la_frecuencia_de_las_actualizaciones(crear_cliente, equipo: Equipo) -> None:
    cliente = crear_cliente(limite_actualizacion_cuenta=2)
    habilitar(base_de(cliente), equipo.gerente.id)
    ingresar(cliente, equipo.gerente.usuario, equipo.gerente.contrasena)
    intento = {"nombre_usuario": "otro.usuario", "contrasena_actual": "Incorrecta123"}

    codigos = [cliente.post(USUARIO, json=intento).status_code for _ in range(3)]

    assert codigos == [400, 400, 429]
