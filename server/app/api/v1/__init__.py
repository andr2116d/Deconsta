from fastapi import APIRouter

from app.acceso.infraestructura.http.rutas import router as acceso
from app.acceso.infraestructura.http.rutas_cuenta import router as cuenta
from app.acceso.infraestructura.http.rutas_equipo import router as equipo
from app.categorias.infraestructura.http.rutas import router as categorias
from app.documentos.infraestructura.http.rutas import router as documentos
from app.notificaciones.infraestructura.http.rutas import router as notificaciones
from app.reglas.infraestructura.http.rutas import router as reglas

router = APIRouter()
router.include_router(acceso)
router.include_router(cuenta)
router.include_router(equipo)
router.include_router(categorias)
router.include_router(reglas)
router.include_router(documentos)
router.include_router(notificaciones)
