"""Rutas de las notificaciones. Cada cuenta con la incorporación completa ve y marca solo las suyas;
una notificación de otra cuenta responde 404 NOTIFICACION_NO_ENCONTRADA.

`GET /notificaciones/flujo` es un flujo de eventos (Server-Sent Events): envía `notificacion` con el
id de cada nueva y un comentario de latido cada 20 segundos para que los proxys no corten la
conexión. Cada minuto vuelve a comprobar la sesión: si se cerró o venció, termina el flujo.
"""

import time
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.acceso.dominio.errores import ErrorAcceso
from app.acceso.infraestructura.http.dependencias import ContenedorDep, SesionHabilitadaDep
from app.acceso.infraestructura.http.rutas import ERRORES
from app.notificaciones.infraestructura.http.esquemas import BandejaSalida, MarcadasSalida

router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])

LATIDO_SEGUNDOS = 20
REVISION_SESION_SEGUNDOS = 60


@router.get("", responses=ERRORES)
def listar(sesion: SesionHabilitadaDep, contenedor: ContenedorDep) -> BandejaSalida:
    return BandejaSalida.desde(contenedor.listar_notificaciones.ejecutar(sesion))


@router.post("/lectura", responses=ERRORES)
def marcar_todas(sesion: SesionHabilitadaDep, contenedor: ContenedorDep) -> MarcadasSalida:
    return MarcadasSalida(marcadas=contenedor.marcar_todas_leidas.ejecutar(sesion))


@router.post(
    "/{notificacion_id}/lectura", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORES
)
def marcar(notificacion_id: UUID, sesion: SesionHabilitadaDep, contenedor: ContenedorDep) -> None:
    contenedor.marcar_leida.ejecutar(sesion, notificacion_id)


@router.get("/flujo", responses=ERRORES)
async def flujo(
    request: Request, sesion: SesionHabilitadaDep, contenedor: ContenedorDep
) -> StreamingResponse:
    token = request.cookies.get(contenedor.config.cookie_sesion_nombre)

    async def sesion_vigente() -> bool:
        try:
            await run_in_threadpool(contenedor.autenticar.ejecutar, token)
        except ErrorAcceso:
            return False
        return True

    async def eventos() -> AsyncIterator[str]:
        # La sugerencia de reconexión va primero: si la conexión se corta, el navegador vuelve.
        yield "retry: 5000\n\n"
        ultimo_latido = ultima_revision = time.monotonic()
        async for aviso in contenedor.suscriptor_avisos.escuchar(sesion.usuario.id):
            if await request.is_disconnected():
                break
            ahora = time.monotonic()
            if ahora - ultima_revision >= REVISION_SESION_SEGUNDOS:
                if not await sesion_vigente():
                    break
                ultima_revision = ahora
            if aviso:
                yield f"event: notificacion\ndata: {aviso}\n\n"
            elif ahora - ultimo_latido >= LATIDO_SEGUNDOS:
                yield ": latido\n\n"
                ultimo_latido = ahora

    return StreamingResponse(
        eventos(),
        media_type="text/event-stream",
        # Sin búfer en proxys como Caddy o Nginx: cada evento sale en cuanto se genera.
        headers={"X-Accel-Buffering": "no"},
    )
