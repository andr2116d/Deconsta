"""Rutas de los pagos, sus comprobantes y el bloqueo del registro de pagos.

Ver lo que falta pagar, subir comprobantes y registrar pagos: el gerente y todas sus asistentes con
la incorporación completa. Un comprobante lo ven quien lo subió y el gerente; cualquier otro
responde 404 COMPROBANTE_NO_ENCONTRADO. La confianza de un pago solo la ve el gerente. Confirmar o
devolver un pago y ver o levantar bloqueos: solo el gerente (403 SIN_PERMISO).

`POST /pagos/comprobantes` recibe el archivo (multipart: `archivo` hasta 10 MB, `deuda_id`,
`cuota` y, para la prueba de una mora, `proposito=mora`) y responde 202 con el comprobante
«analizando»: el análisis corre en el worker y se consulta con `GET /pagos/comprobantes/{id}`.

Errores propios: 403 REGISTRO_PAGOS_BLOQUEADO (con `blocked_since`); 404 DEUDA_NO_ENCONTRADA,
PAGO_NO_ENCONTRADO, COMPROBANTE_NO_ENCONTRADO, BLOQUEO_NO_ENCONTRADO y CUENTA_NO_ENCONTRADA; 409
DEUDA_POR_AUTORIZAR, DEUDA_NO_SE_PAGA, CUOTA_YA_PAGADA, MORA_POR_APROBAR, CUOTA_NO_VENCIDA,
MORA_YA_DECLARADA, COMPROBANTE_DE_MORA, COMPROBANTE_EN_ANALISIS,
COMPROBANTE_ILEGIBLE, COMPROBANTE_RECHAZADO, COMPROBANTE_REPETIDO, COMPROBANTE_FALLIDO,
COMPROBANTE_YA_USADO, COMPROBANTE_DE_OTRA_CUOTA y ESTADO_NO_PERMITE; 413 ARCHIVO_DEMASIADO_GRANDE;
422 CAMPOS_OBLIGATORIOS, DATOS_INVALIDOS, ARCHIVO_INVALIDO, COMPROBANTES_NO_COMBINAN e
IMPORTE_NO_COINCIDE; 429 DEMASIADAS_SOLICITUDES; 503 SERVICIO_NO_DISPONIBLE.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.acceso.dominio.modelos import Rol
from app.acceso.infraestructura.http.dependencias import (
    ContenedorDep,
    GerenteDep,
    SesionHabilitadaDep,
)
from app.acceso.infraestructura.http.rutas import ERRORES
from app.deudas.dominio.modelos import EstadoPago
from app.documentos.dominio.errores import ArchivoDemasiadoGrande, ArchivoFaltante
from app.documentos.dominio.modelos import TAMANO_MAXIMO
from app.documentos.infraestructura.http.rutas import CSP_ARCHIVO
from app.pagos.aplicacion.pagos import ComprobanteConsultado
from app.pagos.dominio.modelos import Proposito
from app.pagos.infraestructura.http.esquemas import (
    BloqueoPagosSalida,
    ComprobanteSalida,
    MotivoEntrada,
    PagoDetalleSalida,
    PagoEntrada,
    PagoSalida,
    PorPagarSalida,
)

router = APIRouter(tags=["pagos"])


@router.get("/pagos/por-pagar", responses=ERRORES)
def por_pagar(sesion: SesionHabilitadaDep, contenedor: ContenedorDep) -> PorPagarSalida:
    """La próxima cuota sin pagar de cada deuda registrada del espacio, con el día de hoy."""
    return PorPagarSalida.desde(contenedor.listar_por_pagar.ejecutar(sesion))


@router.post(
    "/pagos/comprobantes",
    status_code=status.HTTP_202_ACCEPTED,
    responses={**ERRORES, 413: {}, 503: {}},
)
async def subir_comprobante(
    sesion: SesionHabilitadaDep,
    contenedor: ContenedorDep,
    archivo: Annotated[UploadFile | None, File()] = None,
    deuda_id: Annotated[UUID | None, Form()] = None,
    cuota: Annotated[int | None, Form(ge=1, le=360)] = None,
    proposito: Annotated[Proposito, Form()] = Proposito.PAGO,
) -> ComprobanteSalida:
    """El voucher de un pago o, con `proposito=mora`, la prueba de la mora de la cuota."""
    if archivo is None:
        raise ArchivoFaltante()
    contenido = await archivo.read(TAMANO_MAXIMO + 1)
    if len(contenido) > TAMANO_MAXIMO:
        raise ArchivoDemasiadoGrande()
    comprobante = await run_in_threadpool(
        contenedor.subir_comprobante.ejecutar,
        sesion,
        deuda_id,
        cuota,
        contenido,
        archivo.filename,
        proposito,
    )
    return ComprobanteSalida.desde(ComprobanteConsultado(comprobante, registro_bloqueado=False))


@router.get("/pagos/comprobantes/{comprobante_id}", responses=ERRORES)
def consultar_comprobante(
    comprobante_id: UUID, sesion: SesionHabilitadaDep, contenedor: ContenedorDep
) -> ComprobanteSalida:
    return ComprobanteSalida.desde(
        contenedor.consultar_comprobante.ejecutar(sesion, comprobante_id)
    )


@router.get("/pagos/comprobantes/{comprobante_id}/contenido", responses=ERRORES)
def contenido_comprobante(
    comprobante_id: UUID, sesion: SesionHabilitadaDep, contenedor: ContenedorDep
) -> Response:
    """El archivo descifrado, solo para quien puede verlo, sin caché ni permisos para scripts."""
    archivo = contenedor.leer_comprobante.ejecutar(sesion, comprobante_id)
    return Response(
        archivo.contenido,
        media_type=archivo.tipo.value,
        headers={
            "Content-Disposition": f'inline; filename="comprobante.{archivo.tipo.extension}"',
            "Content-Security-Policy": CSP_ARCHIVO,
        },
    )


@router.post("/pagos", status_code=status.HTTP_201_CREATED, responses=ERRORES)
def registrar_pago(
    entrada: PagoEntrada, sesion: SesionHabilitadaDep, contenedor: ContenedorDep
) -> PagoSalida:
    return PagoSalida.desde(
        contenedor.registrar_pago.ejecutar(
            sesion, entrada.deuda_id, entrada.cuota, entrada.comprobantes
        ),
        gerente=sesion.usuario.rol is Rol.GERENTE,
    )


@router.get("/pagos", responses=ERRORES)
def listar_pagos(
    sesion: SesionHabilitadaDep, contenedor: ContenedorDep, estado: EstadoPago | None = None
) -> list[PagoSalida]:
    """Los pagos del espacio, los más recientes primero; con `estado`, solo esos."""
    gerente = sesion.usuario.rol is Rol.GERENTE
    return [
        PagoSalida.desde(p, gerente=gerente)
        for p in contenedor.listar_pagos.ejecutar(sesion, estado=estado)
    ]


@router.get("/pagos/{pago_id}", responses=ERRORES)
def consultar_pago(
    pago_id: UUID, sesion: SesionHabilitadaDep, contenedor: ContenedorDep
) -> PagoDetalleSalida:
    return PagoDetalleSalida.detalle(
        contenedor.consultar_pago.ejecutar(sesion, pago_id),
        gerente=sesion.usuario.rol is Rol.GERENTE,
    )


@router.post("/pagos/{pago_id}/confirmacion", responses=ERRORES)
def confirmar_pago(
    pago_id: UUID, sesion: GerenteDep, contenedor: ContenedorDep
) -> PagoDetalleSalida:
    contenedor.confirmar_pago.ejecutar(sesion, pago_id)
    return consultar_pago(pago_id, sesion, contenedor)


@router.post("/pagos/{pago_id}/devolucion", responses=ERRORES)
def devolver_pago(
    pago_id: UUID, entrada: MotivoEntrada, sesion: GerenteDep, contenedor: ContenedorDep
) -> PagoDetalleSalida:
    contenedor.devolver_pago.ejecutar(sesion, pago_id, entrada.motivo)
    return consultar_pago(pago_id, sesion, contenedor)


@router.get("/registro-pagos/bloqueos", responses=ERRORES)
def bloqueos_pagos(sesion: GerenteDep, contenedor: ContenedorDep) -> list[BloqueoPagosSalida]:
    return [BloqueoPagosSalida.desde(b) for b in contenedor.listar_bloqueos_pagos.ejecutar(sesion)]


@router.post(
    "/registro-pagos/bloqueos/{asistente_id}/levantamiento",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERRORES,
)
def levantar_bloqueo_pagos(
    asistente_id: UUID, sesion: GerenteDep, contenedor: ContenedorDep
) -> None:
    contenedor.levantar_bloqueo_pagos.ejecutar(sesion, asistente_id)
