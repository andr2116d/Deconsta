import base64
import os
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy.engine import make_url

# Las pruebas no dependen del .env de cada desarrollador: claves nuevas en cada ejecución.
os.environ["ENTORNO"] = "pruebas"
os.environ["MIGRAR_AL_INICIAR"] = "false"
os.environ["COOKIE_SEGURA"] = "false"
os.environ["CLAVE_CIFRADO_DATOS"] = base64.b64encode(os.urandom(32)).decode()
os.environ["CLAVE_HUELLA_DATOS"] = base64.b64encode(os.urandom(32)).decode()
REDIS_PRUEBAS = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ["REDIS_URL"] = REDIS_PRUEBAS

URL_PRUEBAS = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/deconsta_test",
)
os.environ["DATABASE_URL"] = URL_PRUEBAS

from app.acceso.dominio.datos_personales import DatosPersonales  # noqa: E402
from app.acceso.dominio.modelos import Rol  # noqa: E402
from app.contenedor import Contenedor  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.migraciones import aplicar_pendientes, conninfo  # noqa: E402
from app.main import crear_app  # noqa: E402


def _admin() -> psycopg.Connection:
    return psycopg.connect(conninfo(URL_PRUEBAS), autocommit=True)


def crear_base(plantilla: str | None = None) -> str:
    """Crea una base vacía (o copia de una plantilla) y devuelve su URL de SQLAlchemy."""
    nombre = f"deconsta_prueba_{uuid.uuid4().hex[:12]}"
    origen = f" TEMPLATE {plantilla}" if plantilla else ""
    with _admin() as conexion:
        conexion.execute(f"CREATE DATABASE {nombre}{origen}".encode())
    return make_url(URL_PRUEBAS).set(database=nombre).render_as_string(hide_password=False)


def eliminar_base(url: str) -> None:
    nombre = make_url(url).database
    with _admin() as conexion:
        conexion.execute(f"DROP DATABASE IF EXISTS {nombre} WITH (FORCE)".encode())


@pytest.fixture
def base_vacia() -> Iterator[str]:
    url = crear_base()
    yield url
    eliminar_base(url)


@pytest.fixture(scope="session")
def plantilla() -> Iterator[str]:
    """Base con todas las migraciones aplicadas; cada prueba trabaja sobre una copia."""
    url = crear_base()
    aplicar_pendientes(url)
    yield str(make_url(url).database)
    eliminar_base(url)


@pytest.fixture
def base(plantilla: str) -> Iterator[str]:
    url = crear_base(plantilla)
    yield url
    eliminar_base(url)


@pytest.fixture
def redis_limpio() -> Iterator[Redis]:
    cliente = Redis.from_url(REDIS_PRUEBAS)
    cliente.flushdb()
    yield cliente
    cliente.flushdb()
    cliente.close()


# Límites amplios por defecto: cada prueba de limitación fija los suyos.
LIMITES_AMPLIOS = {
    "limite_ingreso_por_origen": 1000,
    "limite_ingreso_por_usuario": 1000,
    "limite_cambio_contrasena": 1000,
    "limite_desbloqueo": 1000,
    "limite_actualizacion_cuenta": 1000,
    "limite_gestion_equipo": 1000,
}

FabricaCliente = Callable[..., TestClient]


@pytest.fixture
def crear_cliente(base: str, redis_limpio: Redis) -> Iterator[FabricaCliente]:
    contenedores: list[Contenedor] = []

    def fabricar(**ajustes: Any) -> TestClient:
        config = Settings(database_url=base, **{**LIMITES_AMPLIOS, **ajustes})
        contenedor = Contenedor.crear(config)
        contenedores.append(contenedor)
        return TestClient(crear_app(config, contenedor))

    yield fabricar
    for contenedor in contenedores:
        contenedor.cerrar()


@pytest.fixture
def cliente(crear_cliente: FabricaCliente) -> TestClient:
    return crear_cliente()


@dataclass(frozen=True)
class Cuenta:
    id: uuid.UUID
    usuario: str
    contrasena: str


@dataclass(frozen=True)
class Equipo:
    gerente: Cuenta
    asistente: Cuenta
    otro_gerente: Cuenta


def datos(nombres: str, apellidos: str, documento: str) -> DatosPersonales:
    return DatosPersonales.crear(
        nombres=nombres,
        apellidos=apellidos,
        correo=f"{nombres.lower()}.{documento}@ejemplo.pe",
        tipo_documento="dni",
        numero_documento=documento,
        telefono="987654321",
    )


@pytest.fixture
def equipo(cliente: TestClient) -> Equipo:
    crear = cliente.app.state.contenedor.crear_cuenta  # type: ignore[attr-defined]

    def cuenta(rol: Rol, persona: DatosPersonales, gerente: str | None = None) -> Cuenta:
        creada = crear.ejecutar(rol=rol, datos=persona, gerente_nombre_usuario=gerente)
        return Cuenta(creada.usuario.id, creada.usuario.nombre_usuario, creada.contrasena_temporal)

    gerente = cuenta(Rol.GERENTE, datos("Valentina", "Ramos", "45678912"))
    asistente = cuenta(Rol.ASISTENTE, datos("Lucía", "Vega", "41234567"), gerente.usuario)
    otro = cuenta(Rol.GERENTE, datos("Martín", "Salas", "40000001"))
    return Equipo(gerente, asistente, otro)


def consultar(url: str, sql: str, *parametros: object) -> list[tuple[Any, ...]]:
    with psycopg.connect(conninfo(url)) as conexion:
        cursor = conexion.execute(sql.encode(), parametros or None)
        return cursor.fetchall() if cursor.description else []


def habilitar(url: str, *usuarios: uuid.UUID) -> None:
    """Deja cuentas con la contraseña cambiada y los documentos vigentes aceptados para probar
    rutas de trabajo sin repetir el flujo."""
    with psycopg.connect(conninfo(url)) as conexion:
        for usuario in usuarios:
            conexion.execute(
                "UPDATE usuario SET debe_cambiar_contrasena = false WHERE id = %s", (usuario,)
            )
            conexion.execute(
                "INSERT INTO aceptacion_documento (usuario_id, documento_id)"
                " SELECT %s, id FROM documento_legal ON CONFLICT DO NOTHING",
                (usuario,),
            )
