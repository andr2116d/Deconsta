"""Rutas de «Mi equipo». Solo para gerentes con la incorporación completa (403 SIN_PERMISO o
INCORPORACION_PENDIENTE) y solo sobre las asistentes de su equipo (404 CUENTA_NO_ENCONTRADA para
cualquier otra cuenta).

Errores propios: 409 PERSONA_YA_EN_EQUIPO, ASISTENTE_ELIMINADA (con deleted_account para ofrecer
recuperarla), DATOS_DUPLICADOS, CUENTA_YA_BLOQUEADA, CUENTA_NO_BLOQUEADA y CUENTA_NO_ELIMINADA;
422 DATOS_INVALIDOS y CONTRASENA_INSEGURA; 429 DEMASIADAS_SOLICITUDES.
"""

from uuid import UUID

from fastapi import APIRouter, status

from app.acceso.aplicacion.equipo import NuevaAsistente
from app.acceso.dominio.datos_personales import DatosPersonales
from app.acceso.infraestructura.http.dependencias import ContenedorDep, GerenteDep
from app.acceso.infraestructura.http.esquemas import (
    AsistenteSalida,
    CredencialesSalida,
    MotivoEntrada,
    NuevaAsistenteEntrada,
)
from app.acceso.infraestructura.http.rutas import ERRORES

router = APIRouter(prefix="/asistentes", tags=["equipo"])


@router.get("", responses=ERRORES)
def listar(sesion: GerenteDep, contenedor: ContenedorDep) -> list[AsistenteSalida]:
    return [AsistenteSalida.desde(m) for m in contenedor.listar_equipo.ejecutar(sesion)]


@router.post("", status_code=status.HTTP_201_CREATED, responses=ERRORES)
def registrar(
    entrada: NuevaAsistenteEntrada, sesion: GerenteDep, contenedor: ContenedorDep
) -> CredencialesSalida:
    # El correo lo completa la asistente al confirmar sus datos; el celular es obligatorio.
    datos = DatosPersonales.crear(
        nombres=entrada.nombres,
        apellidos=entrada.apellidos,
        correo=None,
        tipo_documento=entrada.tipo_documento,
        numero_documento=entrada.numero_documento,
        telefono=entrada.telefono,
        correo_obligatorio=False,
        telefono_obligatorio=True,
    )
    nueva = NuevaAsistente(
        datos=datos,
        cargo=entrada.cargo,
        nombre_usuario=(entrada.nombre_usuario or "").strip() or None,
        contrasena=entrada.contrasena or None,
        crear_aunque_eliminada=entrada.crear_aunque_eliminada,
    )
    return CredencialesSalida.desde(contenedor.registrar_asistente.ejecutar(sesion, nueva))


@router.post("/{asistente_id}/bloqueo", responses=ERRORES)
def bloquear(
    asistente_id: UUID,
    sesion: GerenteDep,
    contenedor: ContenedorDep,
    entrada: MotivoEntrada | None = None,
) -> AsistenteSalida:
    motivo = entrada.motivo if entrada else None
    miembro = contenedor.bloquear_asistente.ejecutar(sesion, asistente_id, motivo)
    return AsistenteSalida.desde(miembro)


@router.post("/{asistente_id}/desbloqueo", responses=ERRORES)
def desbloquear(
    asistente_id: UUID,
    sesion: GerenteDep,
    contenedor: ContenedorDep,
    entrada: MotivoEntrada | None = None,
) -> AsistenteSalida:
    motivo = entrada.motivo if entrada else None
    miembro = contenedor.desbloquear_asistente.ejecutar(sesion, asistente_id, motivo)
    return AsistenteSalida.desde(miembro)


@router.post(
    "/{asistente_id}/eliminacion", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORES
)
def eliminar(
    asistente_id: UUID,
    sesion: GerenteDep,
    contenedor: ContenedorDep,
    entrada: MotivoEntrada | None = None,
) -> None:
    motivo = entrada.motivo if entrada else None
    contenedor.eliminar_asistente.ejecutar(sesion, asistente_id, motivo)


@router.post("/{asistente_id}/restablecimiento", responses=ERRORES)
def restablecer_contrasena(
    asistente_id: UUID,
    sesion: GerenteDep,
    contenedor: ContenedorDep,
    entrada: MotivoEntrada | None = None,
) -> CredencialesSalida:
    """Contraseña temporal nueva para una asistente que olvidó la suya. Cierra sus sesiones."""
    motivo = entrada.motivo if entrada else None
    entregadas = contenedor.restablecer_contrasena.ejecutar(sesion, asistente_id, motivo)
    return CredencialesSalida.desde(entregadas)


@router.post("/{asistente_id}/recuperacion", responses=ERRORES)
def recuperar(
    asistente_id: UUID, sesion: GerenteDep, contenedor: ContenedorDep
) -> CredencialesSalida:
    return CredencialesSalida.desde(contenedor.recuperar_asistente.ejecutar(sesion, asistente_id))
