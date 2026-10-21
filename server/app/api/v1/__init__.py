from fastapi import APIRouter

from app.acceso.infraestructura.http.rutas import router as acceso

router = APIRouter()
router.include_router(acceso)
