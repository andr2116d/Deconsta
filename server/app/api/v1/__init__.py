from fastapi import APIRouter

from app.acceso.infraestructura.http.rutas import router as acceso
from app.acceso.infraestructura.http.rutas_cuenta import router as cuenta
from app.acceso.infraestructura.http.rutas_equipo import router as equipo

router = APIRouter()
router.include_router(acceso)
router.include_router(cuenta)
router.include_router(equipo)
