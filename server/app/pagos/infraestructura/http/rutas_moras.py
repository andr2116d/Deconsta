"""Rutas de la mora de una cuota vencida.

Declararla: el gerente y todas sus asistentes, con la prueba ya analizada (se sube en
`POST /pagos/comprobantes` con `proposito=mora`). La de una asistente espera la aprobación del
gerente y la cuota no se paga mientras tanto. Ver: todo el espacio; la confianza, solo el gerente.
Aprobar o rechazar: solo el gerente (403 SIN_PERMISO).

Se registran antes que las rutas de los pagos: `/pagos/moras` no es el id de un pago.

Errores propios: 403 REGISTRO_PAGOS_BLOQUEADO; 404 DEUDA_NO_ENCONTRADA, MORA_NO_ENCONTRADA y
COMPROBANTE_NO_ENCONTRADO; 409 DEUDA_POR_AUTORIZAR, DEUDA_NO_SE_PAGA, CUOTA_YA_PAGADA,
CUOTA_NO_VENCIDA, MORA_YA_DECLARADA, COMPROBANTE_DE_PAGO, COMPROBANTE_DE_OTRA_CUOTA,
COMPROBANTE_EN_ANALISIS, COMPROBANTE_ILEGIBLE, COMPROBANTE_RECHAZADO, COMPROBANTE_REPETIDO,
COMPROBANTE_FALLIDO, PRUEBA_YA_USADA y ESTADO_NO_PERMITE; 422 CAMPOS_OBLIGATORIOS y
DATOS_INVALIDOS; 429 DEMASIADAS_SOLICITUDES.
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.acceso.dominio.modelos import Rol
from app.acceso.infraestructura.http.dependencias import (
    ContenedorDep,
    GerenteDep,
    SesionHabilitadaDep,
)
from app.acceso.infraestructura.http.rutas import ERRORES
from app.pagos.dominio.modelos import EstadoMora
from app.pagos.infraestructura.http.esquemas import (
    MoraDetalleSalida,
    MoraEntrada,
    MoraSalida,
    MotivoEntrada,
)

router = APIRouter(prefix="/pagos/moras", tags=["pagos"])


@router.post("", status_code=status.HTTP_201_CREATED, responses=ERRORES)
def declarar(
    entrada: MoraEntrada, sesion: SesionHabilitadaDep, contenedor: ContenedorDep
) -> MoraSalida:
    return MoraSalida.desde(
        contenedor.declarar_mora.ejecutar(
            sesion,
            entrada.deuda_id,
            entrada.cuota,
            entrada.importe,
            entrada.prueba_id,
            entrada.nota,
        ),
        gerente=sesion.usuario.rol is Rol.GERENTE,
    )


@router.get("", responses=ERRORES)
def listar(
    sesion: SesionHabilitadaDep, contenedor: ContenedorDep, estado: EstadoMora | None = None
) -> list[MoraSalida]:
    gerente = sesion.usuario.rol is Rol.GERENTE
    return [
        MoraSalida.desde(m, gerente=gerente)
        for m in contenedor.listar_moras.ejecutar(sesion, estado=estado)
    ]


@router.get("/{mora_id}", responses=ERRORES)
def consultar(
    mora_id: UUID, sesion: SesionHabilitadaDep, contenedor: ContenedorDep
) -> MoraDetalleSalida:
    return MoraDetalleSalida.detalle(
        contenedor.consultar_mora.ejecutar(sesion, mora_id),
        gerente=sesion.usuario.rol is Rol.GERENTE,
    )


@router.post("/{mora_id}/aprobacion", responses=ERRORES)
def aprobar(mora_id: UUID, sesion: GerenteDep, contenedor: ContenedorDep) -> MoraDetalleSalida:
    contenedor.aprobar_mora.ejecutar(sesion, mora_id)
    return consultar(mora_id, sesion, contenedor)


@router.post("/{mora_id}/rechazo", responses=ERRORES)
def rechazar(
    mora_id: UUID, entrada: MotivoEntrada, sesion: GerenteDep, contenedor: ContenedorDep
) -> MoraDetalleSalida:
    contenedor.rechazar_mora.ejecutar(sesion, mora_id, entrada.motivo)
    return consultar(mora_id, sesion, contenedor)
