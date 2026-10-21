"""Rutas de las reglas de autorización. Solo para el gerente con la incorporación completa
(403 SIN_PERMISO o INCORPORACION_PENDIENTE); un titular de otro espacio responde 404
TITULAR_NO_ENCONTRADO.

Errores propios: 409 TITULAR_DUPLICADO y LIMITE_TITULARES; 422 CAMPOS_OBLIGATORIOS,
DATOS_INVALIDOS, SIN_CAMBIOS, AUTORIZACION_NO_DECLARADA y TITULAR_ES_GERENTE;
429 DEMASIADAS_SOLICITUDES.
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.acceso.infraestructura.http.dependencias import ContenedorDep, GerenteDep
from app.acceso.infraestructura.http.esquemas import MotivoEntrada
from app.acceso.infraestructura.http.rutas import ERRORES
from app.reglas.infraestructura.http.esquemas import (
    EdicionTitularEntrada,
    EvaluacionEntrada,
    EvaluacionSalida,
    LimiteEntrada,
    ReglasSalida,
    TitularEntrada,
    TitularSalida,
)

router = APIRouter(prefix="/reglas", tags=["reglas"])


@router.get("", responses=ERRORES)
def consultar(sesion: GerenteDep, contenedor: ContenedorDep) -> ReglasSalida:
    return ReglasSalida.desde(contenedor.consultar_reglas.ejecutar(sesion))


@router.post("/limite", responses=ERRORES)
def cambiar_limite(
    entrada: LimiteEntrada, sesion: GerenteDep, contenedor: ContenedorDep
) -> ReglasSalida:
    """Con un importe fija el límite; con null lo quita."""
    contenedor.cambiar_limite.ejecutar(sesion, entrada.limite_importe)
    return ReglasSalida.desde(contenedor.consultar_reglas.ejecutar(sesion))


@router.post("/titulares", status_code=status.HTTP_201_CREATED, responses=ERRORES)
def agregar_titular(
    entrada: TitularEntrada, sesion: GerenteDep, contenedor: ContenedorDep
) -> TitularSalida:
    return TitularSalida.desde(contenedor.agregar_titular.ejecutar(sesion, entrada.nuevo()))


@router.post("/titulares/{titular_id}/edicion", responses=ERRORES)
def editar_titular(
    titular_id: UUID,
    entrada: EdicionTitularEntrada,
    sesion: GerenteDep,
    contenedor: ContenedorDep,
) -> TitularSalida:
    """Cambia nombre y relación. El documento no se edita: se quita y se agrega otro titular."""
    editado = contenedor.editar_titular.ejecutar(
        sesion, titular_id, entrada.nombre, entrada.relacion
    )
    return TitularSalida.desde(editado)


@router.post(
    "/titulares/{titular_id}/eliminacion",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERRORES,
)
def quitar_titular(
    titular_id: UUID,
    sesion: GerenteDep,
    contenedor: ContenedorDep,
    entrada: MotivoEntrada | None = None,
) -> None:
    motivo = entrada.motivo if entrada else None
    contenedor.quitar_titular.ejecutar(sesion, titular_id, motivo)


@router.post("/evaluacion", responses=ERRORES)
def evaluar(
    entrada: EvaluacionEntrada, sesion: GerenteDep, contenedor: ContenedorDep
) -> EvaluacionSalida:
    """Prueba las reglas como si una asistente registrara ese documento. No guarda nada."""
    return EvaluacionSalida.desde(
        contenedor.evaluar_documento.ejecutar(sesion, entrada.documento())
    )
