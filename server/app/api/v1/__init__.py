from fastapi import APIRouter

from app.acceso.infraestructura.http.rutas import router as acceso
from app.acceso.infraestructura.http.rutas_cuenta import router as cuenta
from app.acceso.infraestructura.http.rutas_equipo import router as equipo
from app.categorias.infraestructura.http.rutas import router as categorias
from app.deudas.infraestructura.http.rutas import router as deudas
from app.documentos.infraestructura.http.rutas import router as documentos
from app.notificaciones.infraestructura.http.rutas import router as notificaciones
from app.pagos.infraestructura.http.rutas import router as pagos
from app.pagos.infraestructura.http.rutas_moras import router as moras
from app.pagos.infraestructura.http.rutas_pedidos import router as pedidos
from app.reglas.infraestructura.http.rutas import router as reglas

router = APIRouter()
router.include_router(acceso)
router.include_router(cuenta)
router.include_router(equipo)
router.include_router(categorias)
router.include_router(reglas)
router.include_router(documentos)
router.include_router(deudas)
# Antes que los pagos: /pagos/moras y /pagos/pedidos no son el id de un pago.
router.include_router(moras)
router.include_router(pedidos)
router.include_router(pagos)
router.include_router(notificaciones)
