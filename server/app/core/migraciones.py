"""Migraciones SQL versionadas.

Cada archivo `NNNN_descripcion.sql` de server/migraciones es una versión del esquema. Al arrancar,
la API toma un advisory lock de Postgres para que un solo proceso migre a la vez, compara los
archivos con la tabla migracion_aplicada y ejecuta las pendientes en orden. Cada migración corre en
su propia transacción junto con su registro: si falla, se revierte completa, se detiene el proceso
y la API no arranca con un esquema a medias.

Una migración ya aplicada no se edita: su checksum se compara en cada arranque. Los cambios van en
un archivo nuevo. No se soportan sentencias que no admiten transacción (CREATE INDEX CONCURRENTLY).

Uso manual: `uv run python -m app.core.migraciones [aplicar|estado]`.
"""

import hashlib
import logging
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import psycopg
from sqlalchemy.engine import make_url

logger = logging.getLogger(__name__)

DIRECTORIO = Path(__file__).resolve().parents[2] / "migraciones"
# Identificador del advisory lock: cualquier entero fijo y exclusivo de las migraciones.
CLAVE_BLOQUEO = 7_301_202_601
PATRON_ARCHIVO = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")

CREAR_REGISTRO = """
CREATE TABLE IF NOT EXISTS migracion_aplicada (
    version integer PRIMARY KEY,
    nombre text NOT NULL,
    checksum text NOT NULL,
    aplicada_en timestamptz NOT NULL DEFAULT now(),
    duracion_ms integer NOT NULL
)
"""


class ErrorMigracion(Exception):
    """Las migraciones no pueden aplicarse y el esquema no debe usarse hasta corregirlo."""


@dataclass(frozen=True)
class Migracion:
    version: int
    nombre: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode()).hexdigest()

    @property
    def etiqueta(self) -> str:
        return f"{self.version:04d}_{self.nombre}"


@dataclass(frozen=True)
class Estado:
    aplicadas: list[int]
    pendientes: list[Migracion]


def cargar(directorio: Path = DIRECTORIO) -> list[Migracion]:
    """Lee las migraciones en orden de versión; rechaza nombres inválidos y versiones repetidas."""
    migraciones: dict[int, Migracion] = {}
    for archivo in sorted(directorio.glob("*.sql")):
        coincidencia = PATRON_ARCHIVO.match(archivo.name)
        if coincidencia is None:
            raise ErrorMigracion(
                f"Nombre de migración inválido: {archivo.name}. Usa NNNN_descripcion.sql."
            )
        version = int(coincidencia.group(1))
        if version in migraciones:
            raise ErrorMigracion(f"La versión {version:04d} está repetida en {archivo.name}.")
        migraciones[version] = Migracion(version, coincidencia.group(2), archivo.read_text())
    return [migraciones[v] for v in sorted(migraciones)]


def conninfo(database_url: str) -> str:
    """Convierte la URL de SQLAlchemy (postgresql+psycopg://) en una de psycopg."""
    url = make_url(database_url).set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


def _aplicadas(conexion: psycopg.Connection) -> dict[int, str]:
    filas = conexion.execute("SELECT version, checksum FROM migracion_aplicada").fetchall()
    return {version: checksum for version, checksum in filas}


def _verificar(aplicadas: dict[int, str], migraciones: list[Migracion]) -> list[Migracion]:
    """Comprueba que lo aplicado coincide con los archivos y devuelve las pendientes."""
    por_version = {m.version: m for m in migraciones}
    desconocidas = sorted(set(aplicadas) - set(por_version))
    if desconocidas:
        raise ErrorMigracion(
            f"La base tiene migraciones que no existen en el código: {desconocidas}. "
            "Actualiza el código antes de arrancar."
        )
    for version, checksum in aplicadas.items():
        if por_version[version].checksum != checksum:
            raise ErrorMigracion(
                f"La migración {por_version[version].etiqueta} cambió después de aplicarse. "
                "Restaura el archivo original y crea una migración nueva."
            )
    pendientes = [m for m in migraciones if m.version not in aplicadas]
    if aplicadas and pendientes and pendientes[0].version < max(aplicadas):
        raise ErrorMigracion(
            f"La migración {pendientes[0].etiqueta} es anterior a la última aplicada "
            f"({max(aplicadas):04d}). Renómbrala con una versión mayor."
        )
    return pendientes


def aplicar_pendientes(database_url: str, directorio: Path = DIRECTORIO) -> list[int]:
    """Aplica las migraciones pendientes en orden y devuelve las versiones aplicadas."""
    migraciones = cargar(directorio)
    aplicadas_ahora: list[int] = []
    with psycopg.connect(conninfo(database_url), autocommit=True) as conexion:
        # lock_timeout también limita la espera del advisory lock si otro proceso se cuelga.
        conexion.execute("SET lock_timeout = '60s'")
        try:
            conexion.execute("SELECT pg_advisory_lock(%s)", (CLAVE_BLOQUEO,))
        except psycopg.errors.LockNotAvailable as error:
            raise ErrorMigracion(
                "Otro proceso lleva demasiado tiempo aplicando migraciones."
            ) from error
        conexion.execute("RESET lock_timeout")
        try:
            conexion.execute(CREAR_REGISTRO)
            # Se leen dentro del lock: otro proceso pudo aplicar migraciones mientras esperábamos.
            for migracion in _verificar(_aplicadas(conexion), migraciones):
                inicio = time.monotonic()
                try:
                    with conexion.transaction():
                        conexion.execute(migracion.sql.encode())
                        conexion.execute(
                            "INSERT INTO migracion_aplicada"
                            " (version, nombre, checksum, duracion_ms) VALUES (%s, %s, %s, %s)",
                            (
                                migracion.version,
                                migracion.nombre,
                                migracion.checksum,
                                round((time.monotonic() - inicio) * 1000),
                            ),
                        )
                except psycopg.Error as error:
                    detalle = error.diag.message_primary or type(error).__name__
                    raise ErrorMigracion(
                        f"La migración {migracion.etiqueta} falló y se revirtió: {detalle}"
                    ) from error
                logger.info("Migración %s aplicada", migracion.etiqueta)
                aplicadas_ahora.append(migracion.version)
        finally:
            conexion.execute("SELECT pg_advisory_unlock(%s)", (CLAVE_BLOQUEO,))
    if not aplicadas_ahora:
        logger.info("El esquema ya está en la última versión")
    return aplicadas_ahora


def estado(database_url: str, directorio: Path = DIRECTORIO) -> Estado:
    migraciones = cargar(directorio)
    with psycopg.connect(conninfo(database_url), autocommit=True) as conexion:
        existe = conexion.execute("SELECT to_regclass('migracion_aplicada')").fetchone()
        aplicadas = _aplicadas(conexion) if existe and existe[0] else {}
    return Estado(sorted(aplicadas), _verificar(aplicadas, migraciones))


def main(argumentos: list[str]) -> int:
    from app.core.config import settings

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    orden = argumentos[0] if argumentos else "aplicar"
    try:
        if orden == "aplicar":
            aplicar_pendientes(settings.database_url)
        elif orden == "estado":
            actual = estado(settings.database_url)
            logger.info("Aplicadas: %s", actual.aplicadas or "ninguna")
            logger.info("Pendientes: %s", [m.etiqueta for m in actual.pendientes] or "ninguna")
        else:
            logger.error("Orden desconocida: %s. Usa aplicar o estado.", orden)
            return 2
    except ErrorMigracion as error:
        logger.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
