"""Rutas HTTP del acceso.

Resultados del inicio de sesión: 200 con la sesión (pasos_pendientes indica qué falta del primer
ingreso: aceptar los documentos vigentes; debe_cambiar_contrasena, si sigue la temporal), 422
CAMPOS_OBLIGATORIOS, 401 CREDENCIALES_INCORRECTAS, 423 CUENTA_BLOQUEADA,
429 DEMASIADAS_SOLICITUDES con Retry-After, 503 SERVICIO_NO_DISPONIBLE y 500 ERROR_INTERNO.

Con un paso pendiente, las rutas de trabajo responden 403 INCORPORACION_PENDIENTE con pending_steps.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from app.acceso.infraestructura.http.dependencias import (
    ContenedorDep,
    GerenteDep,
    OrigenDep,
    SesionDep,
    SesionHabilitadaDep,
)
from app.acceso.infraestructura.http.esquemas import (
    AceptacionEntrada,
    CambioContrasenaEntrada,
    DesbloqueoEntrada,
    DesbloqueoSalida,
    DocumentoSalida,
    ErrorSalida,
    EspacioSalida,
    IngresoEntrada,
    IngresoSalida,
    SesionSalida,
    UsuarioSalida,
)

router = APIRouter(tags=["acceso"])

ERRORES: dict[int | str, dict[str, Any]] = {
    codigo: {"model": ErrorSalida} for codigo in (400, 401, 403, 404, 409, 422, 423, 429, 503)
}


@router.post("/auth/login", responses=ERRORES)
def iniciar_sesion(
    datos: IngresoEntrada, response: Response, contenedor: ContenedorDep, ip: OrigenDep
) -> IngresoSalida:
    resultado = contenedor.iniciar_sesion.ejecutar(datos.nombre_usuario, datos.contrasena, ip)
    config = contenedor.config
    response.set_cookie(
        config.cookie_sesion_nombre,
        resultado.token,
        max_age=int((resultado.expira_en - datetime.now(UTC)).total_seconds()),
        httponly=True,
        secure=config.cookie_segura,
        samesite="strict",
        path="/api",
    )
    return IngresoSalida(
        usuario=UsuarioSalida.desde(resultado.usuario),
        debe_cambiar_contrasena=resultado.usuario.debe_cambiar_contrasena,
        pasos_pendientes=list(resultado.pasos_pendientes),
        primer_ingreso=resultado.primer_ingreso,
    )


@router.get("/auth/me", responses=ERRORES)
def sesion(sesion: SesionDep) -> SesionSalida:
    return SesionSalida.desde(sesion)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def cerrar_sesion(request: Request, response: Response, contenedor: ContenedorDep) -> None:
    nombre = contenedor.config.cookie_sesion_nombre
    contenedor.cerrar_sesion.ejecutar(request.cookies.get(nombre))
    response.delete_cookie(nombre, path="/api")


@router.post("/auth/contrasena", responses=ERRORES)
def cambiar_contrasena(
    datos: CambioContrasenaEntrada, sesion: SesionDep, contenedor: ContenedorDep
) -> SesionSalida:
    actualizada = contenedor.cambiar_contrasena.ejecutar(
        sesion, datos.contrasena_actual, datos.contrasena_nueva
    )
    return SesionSalida.desde(actualizada)


@router.get("/documentos-legales", responses=ERRORES)
def documentos_legales(sesion: SesionDep, contenedor: ContenedorDep) -> list[DocumentoSalida]:
    """Versiones vigentes de los términos y la política, con su aceptación por esta cuenta."""
    return [DocumentoSalida.desde(d) for d in contenedor.consultar_documentos.ejecutar(sesion)]


@router.post("/documentos-legales/aceptacion", responses=ERRORES)
def aceptar_documentos(
    datos: AceptacionEntrada, sesion: SesionDep, contenedor: ContenedorDep
) -> SesionSalida:
    aceptados = {d.tipo: d.version for d in datos.documentos}
    return SesionSalida.desde(contenedor.aceptar_documentos.ejecutar(sesion, aceptados))


@router.get("/espacio", responses=ERRORES)
def espacio(sesion: SesionHabilitadaDep) -> EspacioSalida:
    """Punto de entrada al espacio de trabajo. Solo responde a cuentas que completaron su
    incorporación; los módulos de pagos todavía no están disponibles."""
    return EspacioSalida(usuario=UsuarioSalida.desde(sesion.usuario), disponible=False)


@router.post("/asistentes/{asistente_id}/desbloqueo", responses=ERRORES)
def desbloquear_asistente(
    asistente_id: UUID,
    sesion: GerenteDep,
    contenedor: ContenedorDep,
    datos: DesbloqueoEntrada | None = None,
) -> DesbloqueoSalida:
    motivo = datos.motivo if datos else None
    asistente = contenedor.desbloquear_asistente.ejecutar(sesion, asistente_id, motivo)
    return DesbloqueoSalida(
        id=asistente.id, nombre_usuario=asistente.nombre_usuario, bloqueada=asistente.bloqueada
    )
