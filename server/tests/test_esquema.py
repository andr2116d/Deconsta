import uuid
from collections.abc import Iterator

import psycopg
import pytest

from app.core.migraciones import aplicar_pendientes, conninfo


@pytest.fixture
def conexion(base_vacia: str) -> Iterator[psycopg.Connection]:
    aplicar_pendientes(base_vacia)
    with psycopg.connect(conninfo(base_vacia), autocommit=True) as conexion:
        yield conexion


def insertar_usuario(conexion: psycopg.Connection, rol: str, **extra: object) -> uuid.UUID:
    id_ = uuid.uuid4()
    columnas = {
        "id": id_,
        "rol": rol,
        "nombre_usuario": f"u{id_.hex[:10]}",
        "contrasena_hash": "x",
        "nombres_cifrado": b"x",
        "apellidos_cifrado": b"x",
        "correo_cifrado": b"x",
        "correo_huella": id_.bytes,
        "tipo_documento": "dni",
        "numero_documento_cifrado": b"x",
        "numero_documento_huella": id_.bytes,
        **extra,
    }
    nombres = ", ".join(columnas)
    marcadores = ", ".join(["%s"] * len(columnas))
    conexion.execute(
        f"INSERT INTO usuario ({nombres}) VALUES ({marcadores})".encode(),
        list(columnas.values()),
    )
    return id_


@pytest.mark.parametrize(
    "sentencia",
    [
        "UPDATE auditoria SET motivo = 'otro'",
        "DELETE FROM auditoria",
        "TRUNCATE auditoria",
    ],
)
def test_la_auditoria_no_admite_cambios(conexion: psycopg.Connection, sentencia: str) -> None:
    conexion.execute("INSERT INTO auditoria (accion) VALUES ('INGRESO_EXITOSO')")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conexion.execute(sentencia.encode())
    assert conexion.execute("SELECT count(*) FROM auditoria").fetchone() == (1,)


def test_solo_una_asistente_puede_quedar_bloqueada(conexion: psycopg.Connection) -> None:
    gerente = insertar_usuario(conexion, "gerente")
    insertar_usuario(conexion, "asistente", gerente_id=gerente, bloqueada_en="2026-10-21")
    with pytest.raises(psycopg.errors.CheckViolation, match="ck_usuario_bloqueo_asistente"):
        insertar_usuario(conexion, "gerente", bloqueada_en="2026-10-21")


def test_toda_asistente_pertenece_a_un_gerente(conexion: psycopg.Connection) -> None:
    with pytest.raises(psycopg.errors.CheckViolation, match="ck_usuario_rol_gerente"):
        insertar_usuario(conexion, "asistente")


def test_publica_la_primera_version_de_cada_documento(conexion: psycopg.Connection) -> None:
    filas = conexion.execute("SELECT tipo, version FROM documento_legal ORDER BY tipo").fetchall()
    assert filas == [("privacidad", 1), ("terminos", 1)]


@pytest.mark.parametrize(
    "sentencia",
    [
        "UPDATE documento_legal SET titulo = 'otro'",
        "DELETE FROM documento_legal",
        "TRUNCATE documento_legal CASCADE",
        "UPDATE aceptacion_documento SET aceptada_en = now()",
        "DELETE FROM aceptacion_documento",
        "TRUNCATE aceptacion_documento",
    ],
)
def test_documentos_y_aceptaciones_no_admiten_cambios(
    conexion: psycopg.Connection, sentencia: str
) -> None:
    usuario = insertar_usuario(conexion, "gerente")
    conexion.execute(
        "INSERT INTO aceptacion_documento (usuario_id, documento_id)"
        " SELECT %s, id FROM documento_legal",
        (usuario,),
    )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        conexion.execute(sentencia.encode())
    assert conexion.execute("SELECT count(*) FROM aceptacion_documento").fetchone() == (2,)


def test_una_cuenta_acepta_cada_version_una_sola_vez(conexion: psycopg.Connection) -> None:
    usuario = insertar_usuario(conexion, "gerente")
    aceptar = (
        "INSERT INTO aceptacion_documento (usuario_id, documento_id)"
        " SELECT %s, id FROM documento_legal WHERE tipo = 'terminos'"
    )
    conexion.execute(aceptar, (usuario,))
    with pytest.raises(psycopg.errors.UniqueViolation):
        conexion.execute(aceptar, (usuario,))
