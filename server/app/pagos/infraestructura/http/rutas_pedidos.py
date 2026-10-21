"""Rutas de los pedidos de pago: el gerente pide a una asistente que pague una cuota.

Pedir y retirar: solo el gerente (403 SIN_PERMISO), a una asistente activa de su espacio. Ver los
pendientes: la asistente, los suyos; el gerente, los de su espacio. Se registran antes que las
rutas de los pagos: `/pagos/pedidos` no es el id de un pago.

Errores propios: 404 DEUDA_NO_ENCONTRADA, CUENTA_NO_ENCONTRADA y PEDIDO_NO_ENCONTRADO; 409
DEUDA_POR_AUTORIZAR, DEUDA_NO_SE_PAGA, CUOTA_YA_PAGADA, MORA_POR_APROBAR, PEDIDO_YA_HECHO y
ESTADO_NO_PERMITE; 422 DATOS_INVALIDOS; 429 DEMASIADAS_SOLICITUDES.
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.acceso.infraestructura.http.dependencias import (
    ContenedorDep,
    GerenteDep,
    SesionHabilitadaDep,
)
from app.acceso.infraestructura.http.rutas import ERRORES
from app.pagos.infraestructura.http.esquemas import PedidoEntrada, PedidoSalida

router = APIRouter(prefix="/pagos/pedidos", tags=["pagos"])


@router.post("", status_code=status.HTTP_201_CREATED, responses=ERRORES)
def pedir(entrada: PedidoEntrada, sesion: GerenteDep, contenedor: ContenedorDep) -> PedidoSalida:
    return PedidoSalida.desde(
        contenedor.pedir_pago.ejecutar(
            sesion, entrada.deuda_id, entrada.cuota, entrada.asistente_id, entrada.nota
        )
    )


@router.get("", responses=ERRORES)
def pendientes(sesion: SesionHabilitadaDep, contenedor: ContenedorDep) -> list[PedidoSalida]:
    return [PedidoSalida.desde(p) for p in contenedor.listar_pedidos.ejecutar(sesion)]


@router.post("/{pedido_id}/retiro", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORES)
def retirar(pedido_id: UUID, sesion: GerenteDep, contenedor: ContenedorDep) -> None:
    contenedor.retirar_pedido.ejecutar(sesion, pedido_id)
