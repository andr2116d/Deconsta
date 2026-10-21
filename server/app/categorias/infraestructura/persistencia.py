"""Adaptadores de Postgres para las categorías (SQLAlchemy Core sobre psycopg)."""

from types import TracebackType
from typing import Any, Self
from uuid import UUID

from sqlalchemy import Connection, Engine, Row, text
from sqlalchemy.exc import IntegrityError

from app.acceso.infraestructura.persistencia import RegistroAuditoriaSql
from app.categorias.dominio.errores import CategoriaDuplicada
from app.categorias.dominio.modelos import Categoria, Color, Icono

COLUMNAS = """
    id, gerente_id, nombre, descripcion, color, icono, creado_por, creado_en, actualizado_en,
    archivado_en
"""


def _categoria(fila: Row[Any]) -> Categoria:
    return Categoria(
        id=fila.id,
        gerente_id=fila.gerente_id,
        nombre=fila.nombre,
        descripcion=fila.descripcion,
        color=Color(fila.color),
        icono=Icono(fila.icono),
        creado_por=fila.creado_por,
        creado_en=fila.creado_en,
        actualizado_en=fila.actualizado_en,
        archivado_en=fila.archivado_en,
    )


def _duplicada(error: IntegrityError, categoria: Categoria) -> CategoriaDuplicada | None:
    diagnostico = getattr(error.orig, "diag", None)
    if getattr(diagnostico, "constraint_name", None) != "uq_categoria_gerente_nombre":
        return None
    return CategoriaDuplicada(categoria.nombre, None, archivada=False)


class RepositorioCategoriasSql:
    def __init__(self, conexion: Connection) -> None:
        self._conexion = conexion

    def bloquear_espacio(self, gerente_id: UUID) -> bool:
        fila = self._conexion.execute(
            text(
                "SELECT id FROM usuario WHERE id = :id AND rol = 'gerente' FOR UPDATE",
            ),
            {"id": gerente_id},
        ).first()
        return fila is not None

    def del_espacio(self, gerente_id: UUID, *, incluir_archivadas: bool) -> list[Categoria]:
        filtro = "" if incluir_archivadas else " AND archivado_en IS NULL"
        filas = self._conexion.execute(
            text(
                f"SELECT {COLUMNAS} FROM categoria WHERE gerente_id = :gerente_id{filtro}"
                " ORDER BY archivado_en IS NOT NULL, nombre_normalizado"
            ),
            {"gerente_id": gerente_id},
        ).all()
        return [_categoria(fila) for fila in filas]

    def _una(self, condicion: str, parametros: dict[str, Any]) -> Categoria | None:
        fila = self._conexion.execute(
            text(f"SELECT {COLUMNAS} FROM categoria WHERE {condicion}"), parametros
        ).first()
        return _categoria(fila) if fila else None

    def por_id(self, gerente_id: UUID, categoria_id: UUID) -> Categoria | None:
        return self._una(
            "id = :id AND gerente_id = :gerente_id", {"id": categoria_id, "gerente_id": gerente_id}
        )

    def por_clave(self, gerente_id: UUID, clave: str) -> Categoria | None:
        return self._una(
            "gerente_id = :gerente_id AND nombre_normalizado = :clave",
            {"gerente_id": gerente_id, "clave": clave},
        )

    def _contar(self, gerente_id: UUID, filtro: str = "") -> int:
        return int(
            self._conexion.execute(
                text(f"SELECT count(*) FROM categoria WHERE gerente_id = :gerente_id{filtro}"),
                {"gerente_id": gerente_id},
            ).scalar_one()
        )

    def contar_activas(self, gerente_id: UUID) -> int:
        return self._contar(gerente_id, " AND archivado_en IS NULL")

    def contar(self, gerente_id: UUID) -> int:
        return self._contar(gerente_id)

    @staticmethod
    def _columnas(categoria: Categoria) -> dict[str, Any]:
        return {
            "id": categoria.id,
            "nombre": categoria.nombre,
            "nombre_normalizado": categoria.clave,
            "descripcion": categoria.descripcion,
            "color": categoria.color.value,
            "icono": categoria.icono.value,
            "archivado_en": categoria.archivado_en,
        }

    def _ejecutar(self, sql: str, categoria: Categoria, extra: dict[str, Any]) -> None:
        # Un punto de guardado: si choca con la unicidad, la transacción sigue utilizable.
        try:
            with self._conexion.begin_nested():
                self._conexion.execute(text(sql), {**self._columnas(categoria), **extra})
        except IntegrityError as error:
            if duplicada := _duplicada(error, categoria):
                raise duplicada from error
            raise

    def agregar(self, categoria: Categoria) -> None:
        self._ejecutar(
            "INSERT INTO categoria (id, gerente_id, nombre, nombre_normalizado, descripcion,"
            " color, icono, creado_por, creado_en, actualizado_en, archivado_en)"
            " VALUES (:id, :gerente_id, :nombre, :nombre_normalizado, :descripcion, :color,"
            " :icono, :creado_por, :creado_en, :creado_en, :archivado_en)",
            categoria,
            {
                "gerente_id": categoria.gerente_id,
                "creado_por": categoria.creado_por,
                "creado_en": categoria.creado_en,
            },
        )

    def guardar(self, categoria: Categoria) -> None:
        self._ejecutar(
            "UPDATE categoria SET nombre = :nombre, nombre_normalizado = :nombre_normalizado,"
            " descripcion = :descripcion, color = :color, icono = :icono,"
            " archivado_en = :archivado_en WHERE id = :id",
            categoria,
            {},
        )


class UnidadCategoriasSql:
    def __init__(self, motor: Engine) -> None:
        self._motor = motor

    def __enter__(self) -> Self:
        self._conexion = self._motor.connect()
        self._transaccion = self._conexion.begin()
        self.categorias = RepositorioCategoriasSql(self._conexion)
        self.auditoria = RegistroAuditoriaSql(self._conexion)
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        try:
            if tipo is None:
                self._transaccion.commit()
            else:
                self._transaccion.rollback()
        finally:
            self._conexion.close()
