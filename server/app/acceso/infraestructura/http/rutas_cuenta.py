"""Rutas de «Mi cuenta». Solo actúan sobre la cuenta de la sesión y exigen la incorporación
completa (403 INCORPORACION_PENDIENTE si falta).

Errores propios: 422 SIN_CAMBIOS, CONTRASENA_REQUERIDA, DOCUMENTO_NO_MODIFICABLE y
CAMBIO_DOCUMENTO_SIN_CONFIRMAR; 400 CONTRASENA_ACTUAL_INCORRECTA; 409 DATOS_DUPLICADOS y
LIMITE_CAMBIOS_USUARIO (con renews_at); 429 DEMASIADAS_SOLICITUDES.
"""

from fastapi import APIRouter

from app.acceso.dominio.datos_personales import DatosPersonales
from app.acceso.infraestructura.http.dependencias import ContenedorDep, SesionHabilitadaDep
from app.acceso.infraestructura.http.esquemas import (
    CuentaSalida,
    DatosPersonalesEntrada,
    NombreUsuarioEntrada,
)
from app.acceso.infraestructura.http.rutas import ERRORES

router = APIRouter(prefix="/cuenta", tags=["cuenta"])


@router.get("", responses=ERRORES)
def consultar_cuenta(sesion: SesionHabilitadaDep, contenedor: ContenedorDep) -> CuentaSalida:
    return CuentaSalida.desde(contenedor.consultar_cuenta.ejecutar(sesion))


@router.post("/datos", responses=ERRORES)
def actualizar_datos(
    entrada: DatosPersonalesEntrada, sesion: SesionHabilitadaDep, contenedor: ContenedorDep
) -> CuentaSalida:
    nuevos = DatosPersonales.crear(
        nombres=entrada.nombres,
        apellidos=entrada.apellidos,
        correo=entrada.correo,
        tipo_documento=entrada.tipo_documento,
        numero_documento=entrada.numero_documento,
        telefono=entrada.telefono,
        nombre_recibos=entrada.nombre_recibos,
    )
    cuenta = contenedor.actualizar_datos_personales.ejecutar(
        sesion,
        nuevos,
        contrasena_actual=entrada.contrasena_actual,
        confirmar_cambio_documento=entrada.confirmar_cambio_documento,
    )
    return CuentaSalida.desde(cuenta)


@router.post("/nombre-usuario", responses=ERRORES)
def cambiar_nombre_usuario(
    entrada: NombreUsuarioEntrada, sesion: SesionHabilitadaDep, contenedor: ContenedorDep
) -> CuentaSalida:
    cuenta = contenedor.cambiar_nombre_usuario.ejecutar(
        sesion, entrada.nombre_usuario, entrada.contrasena_actual
    )
    return CuentaSalida.desde(cuenta)
