"""Rutas HTTP del acceso.

Resultados del inicio de sesión: 200 con la sesión (debe_cambiar_contrasena indica si toca cambiar
la contraseña inicial), 422 CAMPOS_OBLIGATORIOS, 401 CREDENCIALES_INCORRECTAS, 423 CUENTA_BLOQUEADA,
429 DEMASIADAS_SOLICITUDES con Retry-After, 503 SERVICIO_NO_DISPONIBLE y 500 ERROR_INTERNO.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request, Response, status

from app.acceso.infraestructura.http.dependencias import (
    ContenedorDep,
    OrigenDep,
    SesionDep,
)
from app.acceso.infraestructura.http.esquemas import (
    ErrorSalida,
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
        primer_ingreso=resultado.primer_ingreso,
    )


@router.get("/auth/me", responses=ERRORES)
def sesion(sesion: SesionDep) -> SesionSalida:
    return SesionSalida(
        usuario=UsuarioSalida.desde(sesion.usuario),
        debe_cambiar_contrasena=sesion.usuario.debe_cambiar_contrasena,
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def cerrar_sesion(request: Request, response: Response, contenedor: ContenedorDep) -> None:
    nombre = contenedor.config.cookie_sesion_nombre
    contenedor.cerrar_sesion.ejecutar(request.cookies.get(nombre))
    response.delete_cookie(nombre, path="/api")
