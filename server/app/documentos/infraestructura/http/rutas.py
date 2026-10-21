"""Rutas de los documentos de las deudas y del bloqueo del registro.

Subir y consultar: gerente y asistentes con la incorporación completa. Cada documento lo ve quien
lo subió y el gerente del espacio; el que ya respalda una deuda, también las demás asistentes.
Cualquier otro responde 404 DOCUMENTO_NO_ENCONTRADO.

`POST /documentos` recibe el archivo (multipart, campo `archivo`, hasta 10 MB) y responde 202 con
el documento «analizando»: el análisis corre en el worker y se consulta con `GET /documentos/{id}`.

Errores propios: 403 REGISTRO_DEUDAS_BLOQUEADO; 404 DOCUMENTO_NO_ENCONTRADO,
BLOQUEO_NO_ENCONTRADO y CUENTA_NO_ENCONTRADA; 409 DOCUMENTO_YA_REGISTRADO (con `existing_debt` y
`registration_blocked`); 413 ARCHIVO_DEMASIADO_GRANDE; 422 CAMPOS_OBLIGATORIOS, ARCHIVO_INVALIDO,
ARCHIVO_VACIO, PDF_PROTEGIDO y DEMASIADAS_PAGINAS; 429 DEMASIADAS_SOLICITUDES; 503
SERVICIO_NO_DISPONIBLE.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.acceso.infraestructura.http.dependencias import (
    ContenedorDep,
    GerenteDep,
    SesionHabilitadaDep,
)
from app.acceso.infraestructura.http.rutas import ERRORES
from app.documentos.dominio.errores import ArchivoDemasiadoGrande, ArchivoFaltante
from app.documentos.dominio.modelos import TAMANO_MAXIMO
from app.documentos.infraestructura.http.esquemas import BloqueoSalida, DocumentoSalida

router = APIRouter(tags=["documentos"])

# El archivo se muestra, pero nada en él se ejecuta ni carga recursos de otro origen.
CSP_ARCHIVO = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox"


@router.post(
    "/documentos", status_code=status.HTTP_202_ACCEPTED, responses={**ERRORES, 413: {}, 503: {}}
)
async def subir(
    sesion: SesionHabilitadaDep,
    contenedor: ContenedorDep,
    archivo: Annotated[UploadFile | None, File()] = None,
) -> DocumentoSalida:
    if archivo is None:
        raise ArchivoFaltante()
    contenido = await archivo.read(TAMANO_MAXIMO + 1)
    if len(contenido) > TAMANO_MAXIMO:
        raise ArchivoDemasiadoGrande()
    documento = await run_in_threadpool(
        contenedor.subir_documento.ejecutar, sesion, contenido, archivo.filename
    )
    return DocumentoSalida.desde(documento)


@router.get("/documentos/{documento_id}", responses=ERRORES)
def consultar(
    documento_id: UUID, sesion: SesionHabilitadaDep, contenedor: ContenedorDep
) -> DocumentoSalida:
    return DocumentoSalida.consultado(contenedor.consultar_documento.ejecutar(sesion, documento_id))


@router.get("/documentos/{documento_id}/contenido", responses=ERRORES)
def contenido(
    documento_id: UUID, sesion: SesionHabilitadaDep, contenedor: ContenedorDep
) -> Response:
    """El archivo descifrado, solo para quien puede verlo. No se guarda en caché ni se ejecuta:
    se entrega con su tipo real y sin permisos para scripts."""
    archivo = contenedor.leer_contenido.ejecutar(sesion, documento_id)
    return Response(
        archivo.contenido,
        media_type=archivo.tipo.value,
        headers={
            "Content-Disposition": f'inline; filename="documento.{archivo.tipo.extension}"',
            "Content-Security-Policy": CSP_ARCHIVO,
        },
    )


@router.get("/registro-deudas/bloqueos", responses=ERRORES)
def bloqueos(sesion: GerenteDep, contenedor: ContenedorDep) -> list[BloqueoSalida]:
    return [BloqueoSalida.desde(b) for b in contenedor.listar_bloqueos.ejecutar(sesion)]


@router.post(
    "/registro-deudas/bloqueos/{asistente_id}/levantamiento",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERRORES,
)
def levantar_bloqueo(asistente_id: UUID, sesion: GerenteDep, contenedor: ContenedorDep) -> None:
    contenedor.levantar_bloqueo.ejecutar(sesion, asistente_id)
