from typing import Annotated

from fastapi import Depends, Request

from app.acceso.aplicacion.autenticar import SesionActiva
from app.acceso.dominio.errores import IncorporacionPendiente, SinPermiso
from app.acceso.dominio.modelos import Rol
from app.contenedor import Contenedor


def obtener_contenedor(request: Request) -> Contenedor:
    contenedor: Contenedor = request.app.state.contenedor
    return contenedor


ContenedorDep = Annotated[Contenedor, Depends(obtener_contenedor)]


def origen(request: Request) -> str:
    """IP del cliente. Detrás de un proxy, uvicorn la toma de X-Forwarded-For solo si el proxy está
    en --forwarded-allow-ips; así un cliente no puede inventarse otra IP."""
    return request.client.host if request.client else "desconocido"


OrigenDep = Annotated[str, Depends(origen)]


def sesion_actual(request: Request, contenedor: ContenedorDep) -> SesionActiva:
    token = request.cookies.get(contenedor.config.cookie_sesion_nombre)
    return contenedor.autenticar.ejecutar(token)


SesionDep = Annotated[SesionActiva, Depends(sesion_actual)]


def sesion_habilitada(sesion: SesionDep) -> SesionActiva:
    """Sesión de una cuenta que ya completó su incorporación. Toda ruta de trabajo la exige: con
    un paso pendiente, la sesión solo sirve para completarlo, aunque se llame a la API directo."""
    if sesion.pasos_pendientes:
        raise IncorporacionPendiente(sesion.pasos_pendientes)
    return sesion


SesionHabilitadaDep = Annotated[SesionActiva, Depends(sesion_habilitada)]


def sesion_de_gerente(sesion: SesionHabilitadaDep) -> SesionActiva:
    if sesion.usuario.rol is not Rol.GERENTE:
        raise SinPermiso()
    return sesion


GerenteDep = Annotated[SesionActiva, Depends(sesion_de_gerente)]
