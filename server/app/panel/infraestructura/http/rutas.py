"""Ruta del panel de inicio: `GET /panel`, para el gerente y sus asistentes con la incorporación
completa. Al gerente le responde su resumen (`resumen`); a la asistente, su jornada (`jornada`)."""

from fastapi import APIRouter

from app.acceso.infraestructura.http.dependencias import ContenedorDep, SesionHabilitadaDep
from app.acceso.infraestructura.http.rutas import ERRORES
from app.categorias.aplicacion.categorias import espacio_de
from app.panel.infraestructura.http.esquemas import PanelSalida

router = APIRouter(tags=["panel"])


@router.get("/panel", responses=ERRORES)
def panel(sesion: SesionHabilitadaDep, contenedor: ContenedorDep) -> PanelSalida:
    return PanelSalida.desde(
        contenedor.consultar_panel.ejecutar(sesion), sesion.usuario.rol, espacio_de(sesion)
    )
