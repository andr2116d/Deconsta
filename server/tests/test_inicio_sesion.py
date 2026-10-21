from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from tests.conftest import Equipo, consultar

LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"


def ingresar(cliente: TestClient, usuario: str, contrasena: str) -> tuple[int, dict]:
    respuesta = cliente.post(LOGIN, json={"nombre_usuario": usuario, "contrasena": contrasena})
    return respuesta.status_code, respuesta.json()


def base_de(cliente: TestClient) -> str:
    return cliente.app.state.contenedor.config.database_url  # type: ignore[attr-defined]


def test_ingreso_correcto_crea_una_sesion_en_cookie_httponly(
    cliente: TestClient, equipo: Equipo
) -> None:
    respuesta = cliente.post(
        LOGIN,
        json={
            "nombre_usuario": f"  {equipo.gerente.usuario.upper()} ",
            "contrasena": equipo.gerente.contrasena,
        },
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["usuario"] == {
        "id": str(equipo.gerente.id),
        "nombre_usuario": equipo.gerente.usuario,
        "nombres": "Valentina",
        "rol": "gerente",
    }
    cookie = respuesta.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/api" in cookie
    assert respuesta.headers["cache-control"] == "no-store"
    assert cliente.get(ME).json()["usuario"]["id"] == str(equipo.gerente.id)


@pytest.mark.parametrize(
    ("cuerpo", "campos"),
    [
        (
            {},
            {
                "nombre_usuario": "Ingresa tu nombre de usuario.",
                "contrasena": "Ingresa tu contraseña.",
            },
        ),
        (
            {"nombre_usuario": "   ", "contrasena": "x"},
            {"nombre_usuario": "Ingresa tu nombre de usuario."},
        ),
        ({"nombre_usuario": "ana", "contrasena": ""}, {"contrasena": "Ingresa tu contraseña."}),
    ],
)
def test_campos_obligatorios_ausentes(cliente: TestClient, cuerpo: dict, campos: dict) -> None:
    respuesta = cliente.post(LOGIN, json=cuerpo)

    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "code": "CAMPOS_OBLIGATORIOS",
        "detail": "Completa los campos obligatorios.",
        "fields": campos,
    }


def test_un_cuerpo_que_no_es_json_es_un_dato_invalido(cliente: TestClient) -> None:
    respuesta = cliente.post(
        LOGIN, content="usuario=ana", headers={"content-type": "application/json"}
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["code"] == "DATOS_INVALIDOS"


def test_usuario_inexistente_y_contrasena_incorrecta_responden_igual(
    cliente: TestClient, equipo: Equipo
) -> None:
    inexistente = ingresar(cliente, "nadie.existe", "Cualquiera123")
    incorrecta = ingresar(cliente, equipo.gerente.usuario, "Incorrecta123")

    assert inexistente == incorrecta
    assert inexistente == (
        401,
        {
            "code": "CREDENCIALES_INCORRECTAS",
            "detail": "Usuario o contraseña incorrectos. Revisa los datos e inténtalo de nuevo.",
        },
    )


def test_la_asistente_se_bloquea_al_quinto_intento_fallido(
    cliente: TestClient, equipo: Equipo
) -> None:
    asistente = equipo.asistente
    for _ in range(4):
        assert ingresar(cliente, asistente.usuario, "Incorrecta123")[0] == 401

    estado, cuerpo = ingresar(cliente, asistente.usuario, "Incorrecta123")
    assert estado == 423
    assert cuerpo["code"] == "CUENTA_BLOQUEADA"
    assert "gerente" in cuerpo["detail"]

    # Ni la contraseña correcta, ni otro cliente sin cookies, ni un intento nuevo la desbloquean.
    otro_cliente = TestClient(cliente.app)
    assert ingresar(otro_cliente, asistente.usuario, asistente.contrasena)[0] == 423
    assert ingresar(cliente, asistente.usuario, asistente.contrasena)[0] == 423

    url = base_de(cliente)
    assert consultar(
        url,
        "SELECT intentos_fallidos, bloqueada_en IS NOT NULL FROM usuario WHERE id = %s",
        asistente.id,
    ) == [(5, True)]
    acciones = [
        fila[0]
        for fila in consultar(
            url, "SELECT accion FROM auditoria WHERE cuenta_id = %s ORDER BY id", asistente.id
        )
    ]
    assert acciones.count("CUENTA_BLOQUEADA") == 1
    assert acciones[-2:] == ["INGRESO_RECHAZADO", "INGRESO_RECHAZADO"]


def test_el_gerente_no_se_bloquea_por_intentos_fallidos(
    cliente: TestClient, equipo: Equipo
) -> None:
    for _ in range(7):
        assert ingresar(cliente, equipo.gerente.usuario, "Incorrecta123")[0] == 401

    assert ingresar(cliente, equipo.gerente.usuario, equipo.gerente.contrasena)[0] == 200
    url = base_de(cliente)
    assert consultar(
        url, "SELECT intentos_fallidos, bloqueada_en FROM usuario WHERE id = %s", equipo.gerente.id
    ) == [(0, None)]


def test_un_ingreso_correcto_reinicia_el_contador(cliente: TestClient, equipo: Equipo) -> None:
    asistente = equipo.asistente
    for _ in range(4):
        ingresar(cliente, asistente.usuario, "Incorrecta123")
    assert ingresar(cliente, asistente.usuario, asistente.contrasena)[0] == 200

    for _ in range(4):
        assert ingresar(cliente, asistente.usuario, "Incorrecta123")[0] == 401
    assert ingresar(cliente, asistente.usuario, asistente.contrasena)[0] == 200


def test_intentos_simultaneos_bloquean_una_sola_vez_y_sin_perder_intentos(
    cliente: TestClient, equipo: Equipo
) -> None:
    asistente = equipo.asistente
    with ThreadPoolExecutor(max_workers=8) as hilos:
        estados = list(
            hilos.map(lambda _: ingresar(cliente, asistente.usuario, "Incorrecta123")[0], range(12))
        )

    # El FOR UPDATE serializa los intentos: exactamente 4 fallan, el 5.º bloquea y el resto ya
    # encuentra la cuenta bloqueada.
    assert sorted(estados) == [401] * 4 + [423] * 8
    url = base_de(cliente)
    assert consultar(url, "SELECT intentos_fallidos FROM usuario WHERE id = %s", asistente.id) == [
        (5,)
    ]
    assert consultar(url, "SELECT count(*) FROM auditoria WHERE accion = 'CUENTA_BLOQUEADA'") == [
        (1,)
    ]


def test_primer_ingreso_de_ambos_roles_pide_cambiar_la_contrasena(
    cliente: TestClient, equipo: Equipo
) -> None:
    for cuenta in (equipo.gerente, equipo.asistente):
        estado, cuerpo = ingresar(cliente, cuenta.usuario, cuenta.contrasena)
        assert estado == 200
        assert cuerpo["primer_ingreso"] is True
        assert cuerpo["debe_cambiar_contrasena"] is True

        # Omitir el cambio solo deja un recordatorio: el siguiente ingreso lo vuelve a pedir.
        estado, cuerpo = ingresar(cliente, cuenta.usuario, cuenta.contrasena)
        assert cuerpo["primer_ingreso"] is False
        assert cuerpo["debe_cambiar_contrasena"] is True


def test_las_rutas_protegidas_exigen_una_sesion_valida(cliente: TestClient, equipo: Equipo) -> None:
    assert cliente.get(ME).json()["code"] == "NO_AUTENTICADO"

    cliente.cookies.set("deconsta_sesion", "token-inventado", path="/api")
    respuesta = cliente.get(ME)
    assert respuesta.status_code == 401
    assert 'deconsta_sesion=""' in respuesta.headers["set-cookie"]


def test_cerrar_sesion_invalida_el_token(cliente: TestClient, equipo: Equipo) -> None:
    ingresar(cliente, equipo.gerente.usuario, equipo.gerente.contrasena)
    token = cliente.cookies.get("deconsta_sesion")

    assert cliente.post("/api/v1/auth/logout").status_code == 204
    cliente.cookies.set("deconsta_sesion", token, path="/api")
    assert cliente.get(ME).status_code == 401


def test_la_sesion_vencida_ya_no_autentica(crear_cliente, equipo: Equipo) -> None:
    cliente = crear_cliente()
    ingresar(cliente, equipo.gerente.usuario, equipo.gerente.contrasena)
    consultar(
        base_de(cliente),
        "UPDATE sesion SET creada_en = now() - interval '2 days',"
        " expira_en = now() - interval '1 day'",
    )
    assert cliente.get(ME).status_code == 401


def test_los_datos_personales_quedan_cifrados_en_la_base(
    cliente: TestClient, equipo: Equipo
) -> None:
    fila = consultar(
        base_de(cliente),
        "SELECT nombres_cifrado, correo_cifrado, numero_documento_cifrado, telefono_cifrado,"
        " contrasena_hash FROM usuario WHERE id = %s",
        equipo.gerente.id,
    )[0]
    contenido = b"".join(bytes(valor) for valor in fila[:4])
    for dato in (b"Valentina", b"45678912", b"987654321", b"ejemplo.pe"):
        assert dato not in contenido
    assert fila[4].startswith("$argon2id$")
    assert equipo.gerente.contrasena not in fila[4]
