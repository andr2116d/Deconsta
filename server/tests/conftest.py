import os
import uuid
from collections.abc import Iterator

import psycopg
import pytest
from sqlalchemy.engine import make_url

# Las pruebas no dependen del .env de cada desarrollador.
os.environ["ENTORNO"] = "pruebas"
os.environ["MIGRAR_AL_INICIAR"] = "false"

URL_PRUEBAS = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/deconsta_test",
)
os.environ["DATABASE_URL"] = URL_PRUEBAS

from app.core.migraciones import conninfo  # noqa: E402


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
