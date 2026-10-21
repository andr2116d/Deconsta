"""Rutas de las categorías del espacio.

Consultar: gerente y asistentes con la incorporación completa; las asistentes solo ven las activas.
Crear, editar, archivar y reactivar: solo el gerente (403 SIN_PERMISO). Una categoría de otro
espacio responde 404 CATEGORIA_NO_ENCONTRADA.

Errores propios: 409 CATEGORIA_DUPLICADA (con existing_category si la otra está archivada),
LIMITE_CATEGORIAS, CATEGORIA_ARCHIVADA, CATEGORIA_YA_ARCHIVADA y CATEGORIA_NO_ARCHIVADA;
422 CAMPOS_OBLIGATORIOS, DATOS_INVALIDOS y SIN_CAMBIOS; 429 DEMASIADAS_SOLICITUDES.
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.acceso.infraestructura.http.dependencias import (
    ContenedorDep,
    GerenteDep,
    SesionHabilitadaDep,
)
from app.acceso.infraestructura.http.esquemas import MotivoEntrada
from app.acceso.infraestructura.http.rutas import ERRORES
from app.categorias.infraestructura.http.esquemas import CategoriaEntrada, CategoriaSalida

router = APIRouter(prefix="/categorias", tags=["categorias"])


@router.get("", responses=ERRORES)
def listar(
    sesion: SesionHabilitadaDep, contenedor: ContenedorDep, archivadas: bool = False
) -> list[CategoriaSalida]:
    categorias = contenedor.listar_categorias.ejecutar(sesion, incluir_archivadas=archivadas)
    return [CategoriaSalida.desde(c) for c in categorias]


@router.post("", status_code=status.HTTP_201_CREATED, responses=ERRORES)
def crear(
    entrada: CategoriaEntrada, sesion: GerenteDep, contenedor: ContenedorDep
) -> CategoriaSalida:
    return CategoriaSalida.desde(contenedor.crear_categoria.ejecutar(sesion, entrada.nueva()))


@router.post("/{categoria_id}/edicion", responses=ERRORES)
def editar(
    categoria_id: UUID, entrada: CategoriaEntrada, sesion: GerenteDep, contenedor: ContenedorDep
) -> CategoriaSalida:
    """Reemplaza nombre y descripción. Sin color o sin ícono, se conservan los actuales."""
    editada = contenedor.editar_categoria.ejecutar(sesion, categoria_id, entrada.nueva())
    return CategoriaSalida.desde(editada)


@router.post("/{categoria_id}/archivado", responses=ERRORES)
def archivar(
    categoria_id: UUID,
    sesion: GerenteDep,
    contenedor: ContenedorDep,
    entrada: MotivoEntrada | None = None,
) -> CategoriaSalida:
    motivo = entrada.motivo if entrada else None
    archivada = contenedor.archivar_categoria.ejecutar(sesion, categoria_id, motivo)
    return CategoriaSalida.desde(archivada)


@router.post("/{categoria_id}/reactivacion", responses=ERRORES)
def reactivar(categoria_id: UUID, sesion: GerenteDep, contenedor: ContenedorDep) -> CategoriaSalida:
    return CategoriaSalida.desde(contenedor.reactivar_categoria.ejecutar(sesion, categoria_id))
