import threading
from pathlib import Path

import psycopg
import pytest

from app.core.migraciones import (
    ErrorMigracion,
    aplicar_pendientes,
    cargar,
    conninfo,
    estado,
)


def escribir(directorio: Path, nombre: str, sql: str) -> None:
    (directorio / nombre).write_text(sql)


def tablas(url: str) -> set[str]:
    with psycopg.connect(conninfo(url)) as conexion:
        filas = conexion.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
    return {fila[0] for fila in filas}


def versiones(url: str) -> list[int]:
    with psycopg.connect(conninfo(url)) as conexion:
        filas = conexion.execute("SELECT version FROM migracion_aplicada ORDER BY 1").fetchall()
    return [fila[0] for fila in filas]


def test_aplica_en_orden_y_no_repite_las_aplicadas(base_vacia: str, tmp_path: Path) -> None:
    escribir(tmp_path, "0002_crea_b.sql", "CREATE TABLE b (a_id int REFERENCES a(id));")
    escribir(tmp_path, "0001_crea_a.sql", "CREATE TABLE a (id int PRIMARY KEY);")

    assert aplicar_pendientes(base_vacia, tmp_path) == [1, 2]
    assert aplicar_pendientes(base_vacia, tmp_path) == []

    escribir(tmp_path, "0003_crea_c.sql", "CREATE TABLE c (id int);")
    assert aplicar_pendientes(base_vacia, tmp_path) == [3]
    assert {"a", "b", "c"} <= tablas(base_vacia)
    assert versiones(base_vacia) == [1, 2, 3]


def test_una_migracion_fallida_se_revierte_y_detiene_las_siguientes(
    base_vacia: str, tmp_path: Path
) -> None:
    escribir(tmp_path, "0001_crea_a.sql", "CREATE TABLE a (id int);")
    escribir(tmp_path, "0002_falla.sql", "CREATE TABLE parcial (id int);\nSELECT * FROM no_existe;")
    escribir(tmp_path, "0003_crea_c.sql", "CREATE TABLE c (id int);")

    with pytest.raises(ErrorMigracion, match="0002_falla"):
        aplicar_pendientes(base_vacia, tmp_path)

    # La 0001 queda; la 0002 no deja nada a medias y la 0003 no se intenta.
    assert versiones(base_vacia) == [1]
    assert "parcial" not in tablas(base_vacia)
    assert "c" not in tablas(base_vacia)
    assert [m.version for m in estado(base_vacia, tmp_path).pendientes] == [2, 3]


def test_rechaza_una_migracion_aplicada_que_cambio(base_vacia: str, tmp_path: Path) -> None:
    escribir(tmp_path, "0001_crea_a.sql", "CREATE TABLE a (id int);")
    aplicar_pendientes(base_vacia, tmp_path)
    escribir(tmp_path, "0001_crea_a.sql", "CREATE TABLE a (id bigint);")

    with pytest.raises(ErrorMigracion, match="cambió después de aplicarse"):
        aplicar_pendientes(base_vacia, tmp_path)


def test_rechaza_una_base_con_versiones_que_el_codigo_no_conoce(
    base_vacia: str, tmp_path: Path
) -> None:
    escribir(tmp_path, "0001_crea_a.sql", "CREATE TABLE a (id int);")
    escribir(tmp_path, "0002_crea_b.sql", "CREATE TABLE b (id int);")
    aplicar_pendientes(base_vacia, tmp_path)
    (tmp_path / "0002_crea_b.sql").unlink()

    with pytest.raises(ErrorMigracion, match="no existen en el código"):
        aplicar_pendientes(base_vacia, tmp_path)


def test_procesos_simultaneos_aplican_cada_migracion_una_sola_vez(
    base_vacia: str, tmp_path: Path
) -> None:
    # pg_sleep alarga la migración para que los procesos coincidan esperando el lock.
    escribir(tmp_path, "0001_crea_a.sql", "SELECT pg_sleep(0.3);\nCREATE TABLE a (id int);")
    escribir(tmp_path, "0002_crea_b.sql", "CREATE TABLE b (id int);")
    resultados: list[list[int]] = []
    errores: list[BaseException] = []

    def arrancar() -> None:
        try:
            resultados.append(aplicar_pendientes(base_vacia, tmp_path))
        except BaseException as error:
            errores.append(error)

    hilos = [threading.Thread(target=arrancar) for _ in range(4)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert errores == []
    assert sorted(resultados) == [[], [], [], [1, 2]]
    assert versiones(base_vacia) == [1, 2]


@pytest.mark.parametrize(
    ("archivos", "mensaje"),
    [
        ({"1_corto.sql": ""}, "Nombre de migración inválido"),
        ({"0001_Mayus.sql": ""}, "Nombre de migración inválido"),
        ({"0001_uno.sql": "", "0001_otro.sql": ""}, "está repetida"),
    ],
)
def test_rechaza_archivos_mal_nombrados(
    tmp_path: Path, archivos: dict[str, str], mensaje: str
) -> None:
    for nombre, sql in archivos.items():
        escribir(tmp_path, nombre, sql)
    with pytest.raises(ErrorMigracion, match=mensaje):
        cargar(tmp_path)
