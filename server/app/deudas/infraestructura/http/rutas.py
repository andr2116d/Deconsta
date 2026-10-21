"""Rutas de las deudas.

Registrar y consultar: gerente y asistentes con la incorporación completa. El gerente ve las de su
espacio; una asistente, las que registró. Una deuda de otro espacio responde 404
DEUDA_NO_ENCONTRADA. Autorizar, rechazar, dar visto bueno y anular: solo el gerente (403
SIN_PERMISO).

Errores propios: 403 REGISTRO_DEUDAS_BLOQUEADO; 404 DEUDA_NO_ENCONTRADA y DOCUMENTO_NO_ENCONTRADO;
409 DOCUMENTO_EN_ANALISIS, DOCUMENTO_ILEGIBLE, DOCUMENTO_REPETIDO, DOCUMENTO_RECHAZADO,
DOCUMENTO_FALLIDO, DOCUMENTO_YA_USADO y ESTADO_NO_PERMITE; 422 CAMPOS_OBLIGATORIOS,
DATOS_INVALIDOS y CATEGORIA_NO_DISPONIBLE; 429 DEMASIADAS_SOLICITUDES.
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.infraestructura.http.dependencias import (
    ContenedorDep,
    GerenteDep,
    SesionHabilitadaDep,
)
from app.acceso.infraestructura.http.rutas import ERRORES
from app.contenedor import Contenedor
from app.deudas.infraestructura.http.esquemas import (
    DeudaDetalleSalida,
    DeudaEntrada,
    DeudaSalida,
    MotivoObligatorioEntrada,
    RegistroSalida,
)

router = APIRouter(prefix="/deudas", tags=["deudas"])


def _salida(contenedor: Contenedor, sesion: SesionActiva, deuda_id: UUID) -> DeudaDetalleSalida:
    return DeudaDetalleSalida.detalle(contenedor.consultar_deuda.ejecutar(sesion, deuda_id))


@router.post("", status_code=status.HTTP_201_CREATED, responses=ERRORES)
def registrar(
    entrada: DeudaEntrada, sesion: SesionHabilitadaDep, contenedor: ContenedorDep
) -> RegistroSalida:
    registro = contenedor.registrar_deuda.ejecutar(sesion, entrada.nueva())
    detalle = contenedor.consultar_deuda.ejecutar(sesion, registro.deuda.id)
    return RegistroSalida(deuda=DeudaSalida.con_detalle(detalle), avisos=list(registro.avisos))


@router.get("", responses=ERRORES)
def listar(
    sesion: SesionHabilitadaDep, contenedor: ContenedorDep, pendientes: bool = False
) -> list[DeudaSalida]:
    """Con `pendientes=true`, el gerente ve solo lo que espera su autorización o su visto bueno."""
    deudas = contenedor.listar_deudas.ejecutar(sesion, solo_pendientes=pendientes)
    return [DeudaSalida.con_detalle(d) for d in deudas]


@router.get("/{deuda_id}", responses=ERRORES)
def consultar(
    deuda_id: UUID, sesion: SesionHabilitadaDep, contenedor: ContenedorDep
) -> DeudaDetalleSalida:
    return DeudaDetalleSalida.detalle(contenedor.consultar_deuda.ejecutar(sesion, deuda_id))


@router.post("/{deuda_id}/autorizacion", responses=ERRORES)
def autorizar(deuda_id: UUID, sesion: GerenteDep, contenedor: ContenedorDep) -> DeudaDetalleSalida:
    contenedor.autorizar_deuda.ejecutar(sesion, deuda_id)
    return _salida(contenedor, sesion, deuda_id)


@router.post("/{deuda_id}/rechazo", responses=ERRORES)
def rechazar(
    deuda_id: UUID,
    entrada: MotivoObligatorioEntrada,
    sesion: GerenteDep,
    contenedor: ContenedorDep,
) -> DeudaDetalleSalida:
    contenedor.rechazar_deuda.ejecutar(sesion, deuda_id, entrada.motivo)
    return _salida(contenedor, sesion, deuda_id)


@router.post("/{deuda_id}/revision", responses=ERRORES)
def dar_visto_bueno(
    deuda_id: UUID, sesion: GerenteDep, contenedor: ContenedorDep
) -> DeudaDetalleSalida:
    contenedor.dar_visto_bueno.ejecutar(sesion, deuda_id)
    return _salida(contenedor, sesion, deuda_id)


@router.post("/{deuda_id}/anulacion", responses=ERRORES)
def anular(
    deuda_id: UUID,
    entrada: MotivoObligatorioEntrada,
    sesion: GerenteDep,
    contenedor: ContenedorDep,
) -> DeudaDetalleSalida:
    contenedor.anular_deuda.ejecutar(sesion, deuda_id, entrada.motivo)
    return _salida(contenedor, sesion, deuda_id)
